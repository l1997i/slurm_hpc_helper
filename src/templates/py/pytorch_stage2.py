from torchvision import models
import torch
import sys
import time

torch.set_num_threads(4)
torch.set_num_interop_threads(4)

# Ensures that torch uses GPU if available for all operations
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def get_gpu_memory():
    torch.cuda.empty_cache()  # Clear memory cache
    total_memory = torch.cuda.get_device_properties(device).total_memory
    reserved_memory = torch.cuda.memory_reserved(device)
    available_memory = total_memory - reserved_memory
    return reserved_memory, available_memory

def occupy_gpu_memory(size_in_gb):
    num_elements = int(size_in_gb * (1024 ** 3) / 4)  # Each float32 element takes 4 bytes
    dummy_tensor = torch.empty(num_elements, dtype=torch.float32, device=device)
    return dummy_tensor

if __name__ == "__main__":

    print("We are using PyTorch: " + torch.__version__)
    print("Number of GPUs available:", torch.cuda.device_count())
    print()
    if device.type == 'cuda':
        print("The first GPU available is:", torch.cuda.get_device_name(0))
        print()

        print("Testing PyTorch with GPU ....")

        # Load the pretrained AlexNet model directly to GPU
        alexnet = models.alexnet(pretrained=True).to(device)
        print("alexnet init...")

        # Create a random tensor to simulate input data and directly allocate it to GPU
        x = torch.randn(1, 3, 227, 227, device=device)
        print("prepare input feature...")

        try:
            # Perform a forward pass with the model
            y = alexnet(x)
            print("compute y...")

            # Occupy 75% of the available GPU memory, leaving a buffer of 1.8GB
            reserved_memory, available_memory = get_gpu_memory()
            total_memory = reserved_memory + available_memory
            print(f"Total GPU Memory: {total_memory / 1e9} GB")
            print(f"Reserved Memory: {reserved_memory / 1e9} GB")
            print(f"Available Memory: {available_memory / 1e9} GB")

            dummy_tensor = occupy_gpu_memory(available_memory / 1e9 * 0.75 - 1.8)

            # TODO: Replace the infinite loop with actual computation that needs to run.
            # Remove the loop or add a condition to exit the loop when needed.
            while True:
                y = alexnet(x)
                time.sleep(1) #could be used to simulate processing time
        except Exception as e:
            print("GPU computation *** FAILURE ***.")
            print(str(e))
            print()
    else:
        print("CUDA is not available. No GPU will be used.")

    # Output versions for numpy and Python
    print("We are using numpy:", torch.numpy_version)
    print("This is Python:", sys.version)
    