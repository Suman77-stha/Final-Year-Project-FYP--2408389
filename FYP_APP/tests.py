# FYP_APP/tasks.py
import threading
from .lora_trainer import train_lora_model_dynamic

def retrain_lora_async():
    threading.Thread(target=train_lora_model_dynamic).start()