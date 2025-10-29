# exit when any command fails
set -e

# # make sure submodules are updated
# git submodule update --init --recursive

env_name=partcrafter
echo "${ENV_FOLDER}"

# decide software version
source "${ENV_FOLDER}/installed_version.sh"

echo ${INSTALLED_PYTHON_VERSION}
echo ${INSTALLED_CUDA_VERSION}
echo ${INSTALLED_CUDA_ABBREV}
echo ${INSTALLED_GCC_VERSION}
echo ${INSTALLED_PYTORCH_VERSION}
echo ${INSTALLED_TORCHVISION_VERSION}
echo ${INSTALLED_TORCHAUDIO_VERSION}

# create env, install gcc cuda and openblas
conda create --name $env_name --yes python=${INSTALLED_PYTHON_VERSION}
eval "$(conda shell.bash hook)"
conda activate $env_name

conda install -y -c conda-forge sysroot_linux-64=2.17 ffmpeg gxx=${INSTALLED_GCC_VERSION}
conda install -y -c "nvidia/label/cuda-${INSTALLED_CUDA_VERSION}" cuda
conda install -y -c anaconda openblas=0.3.20

conda deactivate
conda activate ${env_name}

conda_home="$(conda info | grep "active env location : " | cut -d ":" -f2-)"
conda_home="${conda_home#"${conda_home%%[![:space:]]*}"}"

echo ${conda_home}

which python
which pip
which nvcc

# Pytorch
pip install torch==${INSTALLED_PYTORCH_VERSION} torchvision==${INSTALLED_TORCHVISION_VERSION} torchaudio==${INSTALLED_TORCHAUDIO_VERSION} --index-url https://download.pytorch.org/whl/${INSTALLED_CUDA_ABBREV}
pip install torch-cluster -f https://data.pyg.org/whl/torch-${INSTALLED_PYTORCH_VERSION}+${INSTALLED_CUDA_ABBREV}.html

# other packages
pip install -r "${ENV_FOLDER}/requirements.txt"
