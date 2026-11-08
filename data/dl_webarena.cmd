@echo off
cd /d "E:\20260928-paper-application of AnyFIM and TensorFIM\kimi_work\05_experiments\data\webarena_raw"
curl -L -C - --retry 8 --retry-delay 5 -o trajectories.zip "https://hf-mirror.com/datasets/Agent-Eval-Refine/Agent-Trajectories/resolve/main/trajectories.zip"
echo DONE_EXIT_%ERRORLEVEL% >> download.log
