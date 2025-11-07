NUM_MACHINES=1
NUM_LOCAL_GPUS=4
MACHINE_RANK=0

WOKRDIR="$(realpath -m -- "$(pwd)/$(dirname "$0")/..")"
export PYTHONPATH=${WOKRDIR}:${PYTHONPATH}
export WANDB_API_KEY="" # Modify this if you use wandb
export WANDB_MODE=offline

accelerate launch \
    --num_machines $NUM_MACHINES \
    --num_processes $(( $NUM_MACHINES * $NUM_LOCAL_GPUS )) \
    --machine_rank $MACHINE_RANK \
    src/train_partcrafter.py \
        --pin_memory \
        --allow_tf32 \
$@
