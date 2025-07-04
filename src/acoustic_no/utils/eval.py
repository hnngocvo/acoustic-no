import torch
from tqdm import tqdm
from neuralop import LpLoss, H1Loss
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
import seaborn as sns
import numpy as np
from tqdm import tqdm

def evaluate_models(models, dataset, device=None, print_results=True):
    """
    Evaluate multiple models on a dataset and return the results.

    Parameters:
    - models (dict): A dictionary where keys are model names and values are the
    model instances.
    - dataset (AcousticDataset): The dataset to evaluate the models on.
    - print_results (bool): Whether to print the results (default True).

    Returns:
    - results (dict): A dictionary where keys are model names and values are
    dictionaries containing evaluation metrics (mse, l2_loss, h1_loss).
    """

    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    for model in models.values():
        model.to(device)
        model.eval()

    # Initialize results dictionary
    results = {
        name: {
            "mse": 0.0,
            "l2_loss": 0.0,
            "h1_loss": 0.0,
            "rel_l2": 0.0,
            "max_error": 0.0,
        }
        for name in models.keys()
    }
    
    # Initialize loss functions
    N = len(dataset)
    mse = torch.nn.MSELoss()
    l2 = LpLoss(d=2, p=2)
    h1 = H1Loss(d=2)
    
    with torch.no_grad():
        # Iterate over the dataset
        for i in tqdm(range(N), desc="Evaluating", unit="sample"):
            data = dataset[i]
            x = data["x"].unsqueeze(0).to(device)
            y_true = data["y"].unsqueeze(0).to(device)

            # Compute predictions and metrics for each model
            for name, model in models.items():
                y_pred = model(x)
                rel_l2 = torch.norm(y_pred - y_true, p=2) / torch.norm(y_true, p=2)
                max_error = torch.max(torch.abs(y_pred - y_true))

                results[name]["mse"] += mse(y_pred, y_true).item()
                results[name]["l2_loss"] += l2(y_pred, y_true).item()
                results[name]["h1_loss"] += h1(y_pred, y_true).item()
                results[name]["rel_l2"] += rel_l2.item()
                results[name]["max_error"] += max_error.item()
        
        # Average the results
        for name in results.keys():
            results[name]["mse"] /= N
            results[name]["l2_loss"] /= N
            results[name]["h1_loss"] /= N
            results[name]["rel_l2"] /= N
            results[name]["max_error"] /= N
    
    # Print the results if required
    if print_results:
        for name, metrics in results.items():
            print("-" * 40)
            print(f"Average results for model '{name}':")
            print(f"  MSE:         {metrics['mse']:.6f}")
            print(f"  L2 Loss:     {metrics['l2_loss']:.6f}")
            print(f"  H1 Loss:     {metrics['h1_loss']:.6f}")
            print(f"  Relative L2: {metrics['rel_l2']:.6f}")
            print(f"  Max Error:   {metrics['max_error']:.6f}")

    return results


def plot_initial_conditions(dataset, index=None, path=None):
    """
    Plot the initial conditions from the dataset.

    Parameters:
    - dataset (AcousticDataset): The dataset containing the initial conditions.
    - index (int, optional): The index of the sample to plot. If None, the middle sample is used.
    - path (str, optional): Path to save the plot. If None, the plot is displayed.
    """
    
    # Display a sample from the dataset
    if index is None:
        index = len(dataset) // 2
    data = dataset[index]
    p = data["y"]
    v = data["v"]
    a = data["a"]

    # Move velocity x and y to r and g channels
    v = v.reshape(-1, 2, v.shape[1], v.shape[2])
    v = v.permute(0, 2, 3, 1)

    # Extend the velocity to 3 channels
    v = torch.cat([v, torch.zeros_like(v[:, :, :, 0:1])], dim=3)

    # Normalize the velocity
    v = (v - v.min()) / (v.max() - v.min())

    # Make plots
    fig, ax = plt.subplots(1, 3, figsize=(15, 5))
    ax[0].imshow(p[0, :, :], interpolation="nearest")
    ax[0].set_title("Pressure")
    ax[1].imshow(v[0, :, :], interpolation="nearest")
    ax[1].set_title("Velocity")
    ax[2].imshow(a[0, :, :], interpolation="nearest")
    ax[2].set_title("Alpha")

    # Save the figure
    if path is not None:
        plt.savefig(path)
    else:
        plt.show()

def plot_inference_results_direct(pred_data, target_data,
                                  path=None, kind="pressure", name=None):
    """
    Plot inference results directly from prediction and target data.
    Used as a helper function for other plotting functions.

    Parameters:
    - pred_data (torch.Tensor): The predicted data from the model.
    - target_data (torch.Tensor): The ground truth data.
    - path (str, optional): Path to save the plot. If None, the plot is displayed.
    - kind (str): Type of plot to create. Options are "pressure", "animation", or "error".
    - name (str, optional): Name to include in the plot title.
    """
    
    name = "" if name is None else f" ({name})"
    pred_data = pred_data.cpu().numpy()
    target_data = target_data.cpu().numpy()

    if kind == "pressure":

        # Plot the last time step of pressure predictions vs ground truth
        fig, ax = plt.subplots(1, 3, figsize=(12, 6))
        ax[0].imshow(pred_data[-1], cmap="viridis", vmin=-10, vmax=10)
        ax[0].set_title("Predicted Pressure")
        ax[1].imshow(target_data[-1], cmap="viridis", vmin=-10, vmax=10)
        ax[1].set_title("Ground Truth Pressure")
        ax[2].imshow(
            pred_data[-1] - target_data[-1],
            cmap="viridis", vmin=-10, vmax=10
        )
        ax[2].set_title("Difference")
        
        fig.suptitle("Pressure Results" + name)
        plt.tight_layout()

        if path is not None:
            plt.savefig(path)
        else:
            plt.show()
    elif kind == "animation":
        print("Creating prediction animation...")

        # Create animation of predictions vs ground truth
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle("Pressure Field Evolution" + name)

        vmin = min(pred_data.min(), target_data.min())
        vmax = max(pred_data.max(), target_data.max())

        im1 = ax1.imshow(pred_data[0], vmin=vmin, vmax=vmax)
        im2 = ax2.imshow(target_data[0], vmin=vmin, vmax=vmax)
        plt.colorbar(im1, ax=ax1)
        plt.colorbar(im2, ax=ax2)

        ax1.set_title("Prediction")
        ax2.set_title("Ground Truth")

        def update(frame):
            im1.set_array(pred_data[frame])
            im2.set_array(target_data[frame])
            return [im1, im2]

        depth = pred_data.shape[0]
        anim = FuncAnimation(fig, update, frames=depth, interval=50, blit=True)
        writer = PillowWriter(fps=60)

        if path is None:
            path = "pressure_evolution.gif"
            
        print(f"Saving animation to {path}")
        anim.save(path, writer=writer)
        plt.close()
        print("Animation saved.")
    elif kind == "error":
        error_evolution = np.abs(pred_data - target_data).mean(axis=(1, 2))

        # Plot error evolution and distribution
        fig, ax = plt.subplots(ncols=2, figsize=(12, 5))
        
        print("Plotting error evolution...")
        ax[0].plot(error_evolution, 'b-', label='Mean Absolute Error')
        ax[0].set_xlabel('Time Step')
        ax[0].set_ylabel('Error')
        ax[0].set_title('Error Evolution Over Time' + name)
        ax[0].legend()
        ax[0].grid(True)

        print("Plotting error distribution...")
        sns.histplot(error_evolution, bins=30, kde=True, ax=ax[1])
        ax[1].set_xlabel('Error Magnitude')
        ax[1].set_ylabel('Count')
        ax[1].set_title('Distribution of Prediction Errors' + name)

        plt.tight_layout()
        if path is not None:
            plt.savefig(path)
        else:
            plt.show()
        plt.close()
        print("Error plots saved.")
    else:
        raise ValueError(f"Unknown kind: {kind}. Choose from 'pressure', 'animation', or 'error'.")
    
def plot_inference_results(model, dataset, 
                           index=None, device=None, path=None,
                           kind="pressure", name=None):
    """
    Plot inference results from a model on a dataset.

    Parameters:
    - model (torch.nn.Module): The model to evaluate.
    - dataset (AcousticDataset): The dataset to evaluate the model on.
    - index (int, optional): The index of the sample to plot. If None, the middle sample is used.
    - device (torch.device, optional): The device to run the model on. If None, uses CUDA if available.
    - path (str, optional): Path to save the plot. If None, the plot is displayed.
    - kind (str): Type of plot to create. Options are "pressure", "animation", or "error".
    - name (str, optional): Name to include in the plot title.
    """
    
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if index is None:
        index = len(dataset) // 2       # Use the middle sample by default
    
    data = dataset[index]
    model.to(device)

    model.eval()
    x = data["x"]
    p = data["y"]

    # Obtain prediction from the model
    with torch.no_grad():
        pred = model(x.unsqueeze(0).to(device))

    pred_data = pred[0]
    target_data = p

    # Plot inference results
    plot_inference_results_direct(
        pred_data, target_data, path=path, kind=kind, name=name
    )

def sample_iterative(
    model, dataset, device=None, path=None,
    kind="pressure", name=None, compute_metrics=False,
    index=None  # Optional index to plot
):
    """
    Sample the model iteratively on the dataset and plot the results.
    In each iteration, the last predicted pressure field is used as the
    initial condition for the next sample.

    Parameters:
    - model (torch.nn.Module): The model to evaluate.
    - dataset (AcousticDataset): The dataset to evaluate the model on.
    - device (torch.device, optional): The device to run the model on. If None, uses CUDA if available.
    - path (str, optional): Path to save the plot. If None, the plot is displayed.
    - kind (str): Type of plot to create. Options are "pressure", "animation", or "error".
    - name (str, optional): Name to include in the plot title.
    - compute_metrics (bool): Whether to compute and print evaluation metrics.
    - index (int, optional): Functionality differs based on `kind`:
        - "pressure": Index of the sample to plot.
        - "error": Index of the sample to plot.
        - "animation": Up to the specified index for animation.
    """

    model.to(device)
    model.eval()

    # Initialize lists to store true and predicted values
    y_true = []
    y_pred = []
    i = 0

    # Initialize the initial condition from the first sample
    init_cond = dataset[0]["x"][0, :, :].detach().cpu()
    
    # Iterate through the dataset, sampling iteratively
    while i < len(dataset):

        # Get features and target from the dataset
        data = dataset[i]
        x = data["x"].detach().clone()
        p = data["y"]

        # Ensure the initial condition is used for the first sample
        x[0, :, :] = init_cond

        # Predict the next pressure field using the model
        with torch.no_grad():
            pred = model(x.unsqueeze(0).to(device)).squeeze()

        # Set the last predicted pressure field as the new initial condition
        init_cond = pred[-1, :, :].detach().cpu()

        # Append the true and predicted values to the lists
        y_true.append(p[:-1].cpu())
        y_pred.append(pred[:-1].cpu())

        i += dataset.depth - 1  # Skip to the next sample

    # Stack the true and predicted values
    y_true = torch.stack(y_true).flatten(0, 1)[:len(dataset)]
    y_pred = torch.stack(y_pred).flatten(0, 1)[:len(dataset)]

    print(f"Sampled {len(y_true)} initial conditions.")

    if compute_metrics:

        # Evaluate the model on the test dataset
        model.eval()

        # Setup loss functions
        # NOTE: L2 and H1 losses are computed per-sample here so they are
        # the actual relative errors (not over a batch)
        l2loss = LpLoss(d=2, p=2)
        h1loss = H1Loss(d=2)
        mse_criterion = torch.nn.MSELoss()

        total_l2_loss = 0.0
        total_h1_loss = 0.0
        total_mse_loss = 0.0
        total_max_error = 0.0

        for i in tqdm(range(len(dataset)), desc="Evaluating", unit="sample"):
            y, pred = y_true[i], y_pred[i]

            # Calculate losses
            l2 = l2loss(pred, y)
            h1 = h1loss(pred, y)
            mse = mse_criterion(pred, y)

            # Calculate relative L2 error (this is the same as l2)
            #rel_l2 = torch.norm(pred - y, p=2) / torch.norm(y, p=2)

            # Calculate maximum error
            max_error = torch.max(torch.abs(pred - y))

            # Accumulate metrics
            total_l2_loss += l2.item()
            total_h1_loss += h1.item()
            total_mse_loss += mse.item()
            total_max_error += max_error.item()
        
        # Average the metrics
        total_samples = len(dataset)
        avg_l2_loss = total_l2_loss / total_samples
        avg_h1_loss = total_h1_loss / total_samples
        avg_mse_loss = total_mse_loss / total_samples
        avg_max_error = total_max_error / total_samples

        print("-" * 40)
        print(f"Average results for model '{name} (iterative)':")
        print(f"  MSE:       {avg_mse_loss:.6f}")
        print(f"  L2 Loss:   {avg_l2_loss:.6f}")
        print(f"  H1 Loss:   {avg_h1_loss:.6f}")
        print(f"  Max Error: {avg_max_error:.6f}")
    
    if kind == "pressure":

        # Filter to the specified index if provided
        if index is None:
            index = len(dataset) // 2
        y_pred = y_pred[index:index + dataset.depth]
        y_true = y_true[index:index + dataset.depth]

    elif kind == "error" and index is not None:

        # Filter to the specified index if provided
        y_pred = y_pred[index:index + dataset.depth]
        y_true = y_true[index:index + dataset.depth]
    
    elif kind == "animation":

        # Generate animation for `index` steps after middle of dataset
        if index is None:
            index = dataset.depth
        y_pred = y_pred[len(dataset) // 2:len(dataset) // 2 + index]
        y_true = y_true[len(dataset) // 2:len(dataset) // 2 + index]


    plot_inference_results_direct(
        y_pred, y_true, path=path, kind=kind, name=name
    )
