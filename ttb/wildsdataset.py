from scipy.stats import cosine

import matplotlib.pyplot as plt
import numpy as np
import random
import torch
import torchvision.transforms as transforms
import typing
import wilds

# TODO: determine location and scale
def default_sampler(train_len, test_len) -> typing.List:
    perm = []
    total_length = train_len + test_len
    quantiles = np.arange(0, 1, 1 / total_length)
    probabilities = cosine.pdf(quantiles, loc=0, scale=1)

    for p in probabilities:
        if torch.rand(1) < p:
            perm.append(("test", random.randint(0, test_len - 1)))
        else:
            perm.append(("train", random.randint(0, train_len - 1)))

    return perm, probabilities


class WILDSDataset(object):
    def __init__(
        self,
        name: str,
        sampler: typing.Union[str, callable] = "default",
        transform=transforms.Compose([transforms.ToTensor()]),
    ) -> None:
        # Download the dataset
        self.dataset = wilds.get_dataset(name, download=True)
        self.train_data = self.dataset.get_subset("train", transform=transform)
        self.test_data = self.dataset.get_subset("test", transform=transform)

        # Create the ordering of images
        self.permutation, self.probabilities = (
            default_sampler(len(self.train_data), len(self.test_data))
            if sampler == "default"
            else sampler(len(self.train_data), len(self.test_data))
        )
        self.reset()

    def get_loader(
        self, batch_size: int = 16, shuffle: bool = True
    ) -> torch.utils.data.DataLoader:
        return torch.utils.data.DataLoader(
            self.pytorch_ds, batch_size=batch_size, shuffle=shuffle
        )

    def step(self, interval: int = 1) -> None:
        # get all train and test elems in the interval
        if self.ts + interval > len(self.permutation):
            interval = len(self.permutation) - self.ts

        interval_points = self.permutation[self.ts : self.ts + interval]
        train_points = [p for p in interval_points if p[0] == "train"]
        test_points = [p for p in interval_points if p[0] == "test"]

        next_train_ds = torch.utils.data.Subset(
            self.train_data, [p[1] for p in train_points]
        )
        next_test_ds = torch.utils.data.Subset(
            self.test_data, [p[1] for p in test_points]
        )
        self.pytorch_ds = torch.utils.data.ConcatDataset(
            [self.pytorch_ds, next_train_ds, next_test_ds]
        )
        self.ts += interval

    def visualize(self, all: bool = True) -> None:
        probs = self.probabilities if all else self.probabilities[: self.ts]
        plt.plot(range(len(probs)), probs)
        plt.show()

    def reset(self) -> None:
        first_elem = self.permutation[0]
        self.pytorch_ds = (
            torch.utils.data.Subset(self.train_data, [first_elem[1]])
            if first_elem[0] == "train"
            else torch.utils.data.Subset(self.test_data, [first_elem[1]])
        )

        self.ts = 1

    def __len__(self) -> int:
        return len(self.permutation)

    def __getitem__(self, indices):
        if not isinstance(indices, tuple):
            if self.permutation[indices][0] == "train":
                return self.train_data[self.permutation[indices][1]]
            return self.test_data[self.permutation[indices][1]]

        # Return multiple items
        permutation_indices = self.permutation[indices]
        return [
            self.train_data[p[1]] if p[0] == "train" else self.test_data[p[1]]
            for p in permutation_indices
        ]
