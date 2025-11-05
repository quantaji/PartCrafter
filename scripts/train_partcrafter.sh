NUM_MACHINES=1
NUM_LOCAL_GPUS=1
MACHINE_RANK=0

WOKRDIR="$(realpath -m -- "$(pwd)/$(dirname "$0")/..")"
export PYTHONPATH=${WOKRDIR}:${PYTHONPATH}
export WANDB_API_KEY="" # Modify this if you use wandb
export WANDB_MODE=offline
export PYOPENGL_PLATFORM=osmesa 
export LIBGL_ALWAYS_SOFTWARE=1 
export MESA_LOADER_DRIVER_OVERRIDE=swrast 
export OSMESA_LIBRARY=/usr/lib/x86_64-linux-gnu/libOSMesa.so.8 

accelerate launch \
    --num_machines $NUM_MACHINES \
    --num_processes $(( $NUM_MACHINES * $NUM_LOCAL_GPUS )) \
    --machine_rank $MACHINE_RANK \
    src/train_partcrafter.py \
        --pin_memory \
        --allow_tf32 \
$@
