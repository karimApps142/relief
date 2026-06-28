@echo off
REM ============================================================================
REM  setup_env.bat — stand up an ISOLATED ComfyUI env for Microsoft TRELLIS.2
REM  (image -> textured 3D) on a Windows RTX 3060 (Ampere), fully headless.
REM
REM  Separate from the relief stack: its own Python 3.12 + Torch 2.10 + cu130 at
REM  F:\trellis2, so it never touches F:\relief (Torch 2.5.1). Run over SSH:
REM     cd /d F:\relief  &  git pull  &  trellis2\setup_env.bat
REM
REM  Milestone 1: the 5 CUDA-op extensions import -> "ALL TRELLIS EXTENSIONS OK".
REM  Driver must support CUDA 13 (nvidia-smi top-right). Verified on 595.79 / 13.2.
REM ============================================================================
setlocal
title TRELLIS.2 environment setup
set ROOT=F:\trellis2
set PY=F:\Python312\python.exe
set VENV=%ROOT%\.venv\Scripts\python.exe
set W=https://huggingface.co/ayushroutray5777/Trellis_2_RTX3060_2.10.0_cu130/resolve/main

echo(
echo [1/6] Python 3.12 (silent, per-user, no GUI) ...
if not exist "%PY%" (
  curl -L -o "%TEMP%\py312.exe" https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe || goto err
  "%TEMP%\py312.exe" /quiet InstallAllUsers=0 TargetDir=F:\Python312 PrependPath=0 Include_launcher=0 Include_test=0 Shortcuts=0 AssociateFiles=0 || goto err
)
"%PY%" --version || goto err

echo(
echo [2/6] isolated venv ...
if not exist "%VENV%" "%PY%" -m venv "%ROOT%\.venv" || goto err
"%VENV%" -m pip install --upgrade pip || goto err

echo(
echo [3/6] torch 2.10.0 + cu130 (matches your 13.2 driver) ...
"%VENV%" -m pip install torch==2.10.0+cu130 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130 || goto err

echo(
echo [4/6] ComfyUI (separate clone) + deps ...
if not exist "%ROOT%\ComfyUI\main.py" (
  git clone https://github.com/comfyanonymous/ComfyUI.git "%ROOT%\ComfyUI" || goto err
)
"%VENV%" -m pip install -r "%ROOT%\ComfyUI\requirements.txt" || goto err

echo(
echo [5/6] prebuilt RTX 3060 (Ampere) CUDA-op wheels, in order ...
"%VENV%" -m pip install %W%/kaolin-0.18.0-cp312-cp312-win_amd64.whl || goto err
"%VENV%" -m pip install %W%/nvdiffrast-0.4.0-cp312-cp312-win_amd64.whl || goto err
"%VENV%" -m pip install %W%/cumesh-0.0.1-cp312-cp312-win_amd64.whl || goto err
"%VENV%" -m pip install %W%/flex_gemm-1.0.0-cp312-cp312-win_amd64.whl || goto err
REM o_voxel's metadata pins cumesh @ git+...JeffreyXiang/CuMesh, which makes pip try to
REM REBUILD cumesh from source (needs CUDA_HOME). The prebuilt cumesh above already satisfies
REM it at runtime, so install o_voxel's plain deps first, then o_voxel itself with --no-deps.
"%VENV%" -m pip install trimesh zstandard easydict || goto err
"%VENV%" -m pip install --no-deps %W%/o_voxel-0.0.1-cp312-cp312-win_amd64.whl || goto err

echo(
echo [6/6] verify the extensions import ...
"%VENV%" -c "import torch,kaolin,nvdiffrast.torch,cumesh,flex_gemm,o_voxel;print('ALL TRELLIS EXTENSIONS OK')" || goto err

echo(
echo ============================================================
echo   DONE - environment ready. Next: node + models + launch.
echo ============================================================
goto :eof

:err
echo(
echo *** FAILED at the step above (errorlevel %errorlevel%). Copy the error text and send it. ***
exit /b 1
