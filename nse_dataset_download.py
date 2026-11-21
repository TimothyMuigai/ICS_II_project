from pathlib import Path
import shutil
import kagglehub

source = Path(
    kagglehub.dataset_download(
        "macmini62/nairobi-securities-exchangense-stocks-data"
    )
)

destination = Path("data/real/nse/stocks_dataset")
destination.mkdir(parents=True, exist_ok=True)

shutil.copytree(source, destination, dirs_exist_ok=True)

print("Dataset saved to:", destination.resolve())