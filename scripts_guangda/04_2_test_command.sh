# local
bash scripts/train_partcrafter.sh --config scripts_guangda/04_0_train_local_test.yaml --use_ema \
  --gradient_accumulation_steps 4 \
  --output_dir output_partcrafter \
  --tag scaleup_mp8_nt512


#   35g for bs 8,
#   42g for bs 16,
# test for gradient accumulation step
# not chainging usage


# salloc --time=1:30:0 --ntasks=1 --gres=gpu:nvidia_h100_80gb_hbm3_3g.40gb:1 --mem=64G --nodes=1

# apptainer nest
conda_home="$(conda info | grep "active env location : " | cut -d ":" -f2-)"
conda_home="${conda_home#"${conda_home%%[![:space:]]*}"}"

export CUDA_HOST_COMPILER="$conda_home/bin/gcc"
export CUDA_PATH="$conda_home"
export CUDA_HOME=$CUDA_PATH
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:$LD_LIBRARY_PATH"
export PYOPENGL_PLATFORM=osmesa 
export LIBGL_ALWAYS_SOFTWARE=1 
export MESA_LOADER_DRIVER_OVERRIDE=swrast 
export OSMESA_LIBRARY=/usr/lib/x86_64-linux-gnu/libOSMesa.so.8 

bash scripts/train_partcrafter.sh --config scripts_guangda/04_1_train_cc_test.yaml --use_ema \
  --gradient_accumulation_steps 4 \
  --output_dir output_partcrafter \
  --tag scaleup_mp8_nt512
