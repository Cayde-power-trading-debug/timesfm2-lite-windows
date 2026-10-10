# Third-party components

The MIT license at the repository root applies to this tool's original code, not to third-party runtimes, downloaded dependencies or model weights.

## Included in the repository / release

- **CPython 3.11.9 Windows embeddable distribution (amd64)**: original, unmodified ZIP from [python.org](https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip). Its complete license and incorporated-software notices remain in `vendor/python-3.11.9-embed-amd64.zip` as `LICENSE.txt` and are also copied to `third_party_licenses/Python-3.11.9-LICENSE.txt`. The installer changes only the runtime search-path configuration after extraction; no Python binaries are modified.
- **get-pip.py**: unchanged bootstrap snapshot from [bootstrap.pypa.io](https://bootstrap.pypa.io/get-pip.py). SHA256 is recorded in `vendor/integrity.json`. The wrapper's MIT license is preserved in `third_party_licenses/get-pip-LICENSE.txt`. Bundled pip and vendored-dependency notices remain within its original embedded archive. Installed pip version is pinned by the installer.
- **China holiday calendar**: factual 2025/2026 holiday and makeup-workday dates, with official government source links in `calendar/holidays.json` and the maintenance guide. No future year's dates are guessed.

## Downloaded only during installation

- **Google TimesFM**: pinned library version `timesfm==1.3.0` and official TimesFM 2.0 checkpoint `google/timesfm-2.0-500m-pytorch` at revision `dc2443792ce5516872b89b37cf1bc058c3bf0c10`. [Upstream project](https://github.com/google-research/timesfm), Apache License 2.0, with a license copy in `third_party_licenses/TimesFM-Apache-2.0.txt`. [Official model card](https://huggingface.co/google/timesfm-2.0-500m-pytorch). **No weights are redistributed in this repository or release ZIP.**
- **PyTorch 2.6.0**: official CPU or CUDA 12.4 wheels, subject to [PyTorch's license](https://github.com/pytorch/pytorch/blob/main/LICENSE) and included component notices.
- **Other Python dependencies**: pinned direct versions are listed in `requirements.txt`; each dependency retains its own license. Transitive installed versions are recorded by the installer using `pip freeze`.
- **NVIDIA drivers / CUDA libraries / Microsoft VC++ runtime**: no installers or GPU binaries are included in the release. Official packages downloaded or launched by installation tasks remain subject to their respective vendor terms. CUDA runtime libraries may be provided by the selected official PyTorch wheel.

The bundled Python ZIP and pip bootstrap hashes are checked before use. Model downloads are pinned to a revision and the checkpoint is verified against official LFS SHA256 metadata. These checks establish file identity, not model accuracy or third-party endorsement.
