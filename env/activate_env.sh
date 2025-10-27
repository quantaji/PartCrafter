echo ${ENV_FOLDER}

env_name=partcrafter
eval "$(conda shell.bash hook)"
conda activate $env_name
conda_home="$(conda info | grep "active env location : " | cut -d ":" -f2-)"
conda_home="${conda_home#"${conda_home%%[![:space:]]*}"}"

export AM_I_DOCKER=1
export BUILD_WITH_CUDA=1
export CUDA_HOST_COMPILER="$conda_home/bin/gcc"
export CUDA_PATH="$conda_home"
export CUDA_HOME=$CUDA_PATH
export FORCE_CUDA=1
export MAX_JOBS=6
export NLTK_DATA="${ENV_FOLDER}/../3rdparty/nltk_data"
export TORCH_CUDA_ARCH_LIST="7.5 8.0 8.6 8.7 8.9 9.0"

# set software version in environment variable
source ${ENV_FOLDER}/installed_version.sh
