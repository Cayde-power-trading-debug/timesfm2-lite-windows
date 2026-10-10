param(
 [ValidateSet('Install','Runtime','Cuda','Model','Configure','Check','Test','Start','Stop','Driver','HolidayDownload','HolidayApply')][string]$Task='Install',
 [ValidateSet('auto','cpu','gpu')][string]$Device='auto',
 [string]$InstallRoot='', [int]$Port=8899,
 [string]$DriverInstaller='', [string]$DriverUrl='',
 [int]$Year=2027, [string]$NoticeUrl='', [string]$Candidate='', [switch]$Confirmed
)
$ErrorActionPreference='Stop'
$Root=$PSScriptRoot
$HomeDir=if($InstallRoot){[IO.Path]::GetFullPath($InstallRoot)}else{$Root}
$Python=Join-Path $HomeDir 'runtime\python.exe'
$env:PYTHONUTF8='1';$env:PYTHONIOENCODING='utf-8';$env:NOVA_LITE_HOME=$HomeDir
$env:HF_HOME=Join-Path $HomeDir '下载缓存\huggingface';$env:HF_HUB_DISABLE_TELEMETRY='1';$env:HF_HUB_DISABLE_XET='1'
$env:PIP_CACHE_DIR=Join-Path $HomeDir '下载缓存\pip';$env:PIP_DISABLE_PIP_VERSION_CHECK='1'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
function Invoke-Python([string[]]$Arguments) {
 $PreviousPreference=$ErrorActionPreference
 try { $ErrorActionPreference='Continue'; & $Python @Arguments; $ExitLite=$LASTEXITCODE }
 finally { $ErrorActionPreference=$PreviousPreference }
 if($ExitLite -ne 0){throw "Python stage failed (exit $ExitLite). Read the error above."}
}
function Install-Runtime {
 if(-not(Test-Path -LiteralPath $Python)){
  $Zip=Join-Path $Root 'vendor\python-3.11.9-embed-amd64.zip'
  $Integrity=Get-Content -LiteralPath (Join-Path $Root 'vendor\integrity.json') -Raw | ConvertFrom-Json
  if((Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Integrity.python_zip_sha256){throw 'Bundled Python SHA256 mismatch'}
  New-Item -ItemType Directory -Path (Join-Path $HomeDir 'runtime') -Force | Out-Null
  Expand-Archive -LiteralPath $Zip -DestinationPath (Join-Path $HomeDir 'runtime') -Force
 }
 # Relative paths keep the portable runtime independent of drive letters.
 $Pth="python311.zip`r`n.`r`nLib/site-packages`r`n..`r`nimport site`r`n"
 [IO.File]::WriteAllText((Join-Path $HomeDir 'runtime\python311._pth'),$Pth,[Text.Encoding]::ASCII)
 $HasPip=& $Python -c "import importlib.util;print(int(importlib.util.find_spec('pip') is not None))"
 if($HasPip -ne '1'){
  $PipScript=Join-Path $Root 'vendor\get-pip.py'
  $Integrity=Get-Content -LiteralPath (Join-Path $Root 'vendor\integrity.json') -Raw | ConvertFrom-Json
  if((Get-FileHash -LiteralPath $PipScript -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Integrity.get_pip_sha256){throw 'pip bootstrap SHA256 mismatch'}
  Invoke-Python @($PipScript,'pip==25.0.1','setuptools==75.8.2','wheel==0.45.1')
 }
}
function Install-Cuda {
 Install-Runtime
 if(-not(Test-Path -LiteralPath (Join-Path $env:WINDIR 'System32\msvcp140.dll'))){
  $Redist=Join-Path $HomeDir 'vc_redist.x64.exe'
  Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile $Redist -UseBasicParsing
  $SigVC=Get-AuthenticodeSignature -LiteralPath $Redist
  if($SigVC.Status -ne 'Valid' -or $SigVC.SignerCertificate.Subject -notmatch 'Microsoft'){throw 'Invalid Microsoft VC++ runtime signature'}
  $VCProc=Start-Process -FilePath $Redist -ArgumentList '/install','/passive','/norestart' -Verb RunAs -Wait -PassThru
  if($VCProc.ExitCode -notin @(0,3010,1638)){throw "VC++ installer returned $($VCProc.ExitCode)"}
 }
 $Backend='cpu'
 if($Device -ne 'cpu'){
  $Smi=Get-Command nvidia-smi -ErrorAction SilentlyContinue
  if($Smi){
   $Info=& $Smi.Source --query-gpu=driver_version --format=csv,noheader 2>$null
   if($LASTEXITCODE -eq 0 -and $Info){
    $Version=[version](($Info | Select-Object -First 1).Trim())
    if($Version -ge [version]'551.61'){$Backend='cu124'}
   }
  }
  if($Device -eq 'gpu' -and $Backend -eq 'cpu'){throw 'GPU mode requires working NVIDIA driver >=551.61. Use -Task Driver, or -Device cpu.'}
 }
 Write-Host "Installing PyTorch 2.6.0 backend=$Backend (CUDA DLLs are bundled in the cu124 wheel)."
 Invoke-Python @('-m','pip','install','torch==2.6.0','--index-url',"https://download.pytorch.org/whl/$Backend",'--timeout','120')
 Invoke-Python @('-m','pip','install','-r',(Join-Path $Root 'requirements.txt'),'--index-url','https://pypi.org/simple','--timeout','120')
 Invoke-Python @('-m','pip','check')
 Invoke-Python @((Join-Path $Root 'bootstrap.py'),'check','--home',$HomeDir,'--device',$Device)
}
function Install-Driver {
 if(-not $DriverInstaller -and -not $DriverUrl){
  $Smi=Get-Command nvidia-smi -ErrorAction SilentlyContinue
  if($Smi){& $Smi.Source --query-gpu=name,driver_version --format=csv,noheader; if($LASTEXITCODE -eq 0){Write-Host 'Driver is working; no reinstall/downgrade performed.';return}}
  Write-Host 'No usable NVIDIA driver. CPU mode works without a GPU driver.'
  Start-Process 'https://www.nvidia.com/en-us/drivers/'
  throw 'Select the driver for this GPU/Windows version, then rerun -Task Driver -DriverInstaller <official.exe>.'
 }
 if($DriverUrl){
  $Uri=[uri]$DriverUrl
  if($Uri.Scheme -ne 'https' -or $Uri.Host -notin @('us.download.nvidia.com','international.download.nvidia.com','cn.download.nvidia.com','download.nvidia.com')){throw 'Only official NVIDIA driver download hosts are accepted.'}
  New-Item -ItemType Directory -Path (Join-Path $HomeDir '下载缓存') -Force | Out-Null
  $DriverInstaller=Join-Path $HomeDir '下载缓存\nvidia-driver.exe'
  Invoke-WebRequest -Uri $Uri -OutFile $DriverInstaller -UseBasicParsing
 }
 $DriverInstaller=(Resolve-Path -LiteralPath $DriverInstaller).Path
 $Signature=Get-AuthenticodeSignature -LiteralPath $DriverInstaller
 if($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notmatch 'NVIDIA'){throw 'Driver is not validly signed by NVIDIA.'}
 Write-Host 'Launching the official signed driver installer. It may require admin approval and reboot.'
 $Proc=Start-Process -FilePath $DriverInstaller -Verb RunAs -Wait -PassThru
 if($Proc.ExitCode -notin @(0,3010)){throw "Driver installer returned $($Proc.ExitCode)"}
}
try {
 switch($Task){
  'Runtime' {Install-Runtime}
  'Cuda' {Install-Cuda}
  'Driver' {Install-Driver}
  'Model' {Install-Runtime;Invoke-Python @('-m','pip','install','huggingface-hub==0.28.1','--index-url','https://pypi.org/simple');Invoke-Python @((Join-Path $Root 'bootstrap.py'),'model','--home',$HomeDir)}
  'Configure' {Install-Runtime;Invoke-Python @((Join-Path $Root 'bootstrap.py'),'configure','--home',$HomeDir,'--device',$Device)}
  'Check' {Install-Runtime;Invoke-Python @((Join-Path $Root 'bootstrap.py'),'check','--home',$HomeDir,'--device',$Device)}
  'Test' {Invoke-Python @((Join-Path $Root 'bootstrap.py'),'smoke','--home',$HomeDir,'--device',$Device)}
  'Install' {
   if($DriverInstaller -or $DriverUrl){Install-Driver}
   Install-Cuda
   Invoke-Python @((Join-Path $Root 'bootstrap.py'),'model','--home',$HomeDir)
   Invoke-Python @((Join-Path $Root 'bootstrap.py'),'configure','--home',$HomeDir,'--device',$Device)
   Invoke-Python @((Join-Path $Root 'bootstrap.py'),'smoke','--home',$HomeDir,'--device',$Device)
   & $Python -m pip freeze | Set-Content -LiteralPath (Join-Path $HomeDir '已安装依赖锁定.txt') -Encoding UTF8
   Write-Host 'Installation and real prediction check completed. Run 启动.cmd.'
  }
  'Start' {
   if(-not(Test-Path -LiteralPath (Join-Path $HomeDir 'models\timesfm-2.0-500m-pytorch\torch_model.ckpt'))){throw 'Model has not been downloaded. Run 一键安装.cmd first.'}
   Invoke-Python @((Join-Path $Root 'app.py'),'--port',"$Port",'--open')
  }
  'Stop' {
   $PidFile=Join-Path $HomeDir '本地服务.json'
   if(Test-Path -LiteralPath $PidFile){
    $Saved=Get-Content -LiteralPath $PidFile -Raw | ConvertFrom-Json
    $Proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($Saved.pid)"
    if($Proc -and $Proc.CommandLine -like "*$(Join-Path $Root 'app.py')*" -and $Proc.CommandLine -like "*--port $($Saved.port)*"){Stop-Process -Id $Saved.pid;Remove-Item -LiteralPath $PidFile}
    elseif($Proc){throw 'PID now belongs to another process. Refusing to stop it.'}
   }
  }
  'HolidayDownload' {Install-Runtime;Invoke-Python @((Join-Path $Root 'calendar_tools.py'),'download','--year',"$Year",'--url',$NoticeUrl)}
  'HolidayApply' {
   Install-Runtime;$ArgsLite=@((Join-Path $Root 'calendar_tools.py'),'apply','--candidate',$Candidate)
   if($Confirmed){$ArgsLite+='--confirmed'};Invoke-Python $ArgsLite
  }
 }
 exit 0
} catch {Write-Error $_;exit 1}
