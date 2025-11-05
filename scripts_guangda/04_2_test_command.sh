# local
bash scripts/train_partcrafter.sh --config scripts_guangda/04_0_train_local_test.yaml --use_ema \
  --gradient_accumulation_steps 4 \
  --output_dir output_partcrafter \
  --tag scaleup_mp8_nt512


#   35g for bs 8,
#   42g for bs 16,
# test for gradient accumulation step
# not chainging usage

# apptainer nest
bash scripts/train_partcrafter.sh --config scripts_guangda/04_1_train_cc_test.yaml --use_ema \
  --gradient_accumulation_steps 4 \
  --output_dir output_partcrafter \
  --tag scaleup_mp8_nt512
