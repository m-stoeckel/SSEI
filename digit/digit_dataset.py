import os
import tarfile
import warnings
import zipfile
from pathlib import Path
from typing import List

import keras
from p_tqdm import p_map
from sklearn.datasets import fetch_openml
from tqdm import tqdm, trange

from image.image_transforms import *
from image.image_transforms import ImageTransform

INTER_DOWN_HIGH = cv2.INTER_LANCZOS4
INTER_DOWN_FAST = cv2.INTER_NEAREST
INTER_UP_HIGH = cv2.INTER_CUBIC
INTER_UP_FAST = cv2.INTER_AREA

DEBUG = False
# Classmap: {0: OUT, 0..9: #_MACHINE, 10: EMPTY, 11..19: #_HAND}
CLASS_OUT = 0
CLASS_EMPTY = 10


def strip_file_ext(path: str):
    extension = None
    for ext in [".zip", ".tar", ".tar.gz"]:
        if path.endswith(ext):
            extension = ext
    if extension:
        return "".join(list(path)[0:-len(extension)])
    else:
        return path


def char_is_valid_number(char: Union[int, str]):
    if isinstance(char, str):
        char = ord(char)
    return char in [ord(c) for c in '123456789']


class CharacterDataset:
    _digit_offset = 0

    def __init__(
            self,
            resolution,
            shuffle=True,
            fast_resize=False
    ):
        self.res = resolution
        self.shuffle = shuffle
        self.inter_down = INTER_DOWN_FAST if fast_resize else INTER_DOWN_HIGH
        self.inter_up = INTER_UP_FAST if fast_resize else INTER_UP_HIGH

        self.train_x: np.ndarray = np.empty(0, dtype=np.uint8)
        self.train_y: np.ndarray = np.empty(0, dtype=int)
        self.test_x: np.ndarray = np.empty(0, dtype=np.uint8)
        self.test_y: np.ndarray = np.empty(0, dtype=int)

        self.train_indices_by_number: List[np.ndarray] = [np.empty(0, dtype=int)]
        self.test_indices_by_number: List[np.ndarray] = [np.empty(0, dtype=int)]

        self.transforms: List[List[ImageTransform]] = list()

        self._load()

    def _get_label(self, id: Union[int, str]):
        if char_is_valid_number(id):
            return int(chr(id)) + self._digit_offset
        else:
            return CLASS_OUT

    def add_transforms(self, *transforms: ImageTransform):
        """
        Add a transform or a list of sequential transforms to this generator.

        :param transforms: Single ImageTransform or list of sequential ImageTransform
        :return: None
        """
        transforms = list(transforms)
        self.transforms.append(transforms)

    def apply_transforms(self, keep=True):
        if not self.transforms:
            return
        n_train = self.train_x.shape[0]
        n_test = self.test_x.shape[0]
        n_transforms = len(self.transforms)
        new_train_shape = self.train_x.shape * np.array([int(keep) + n_transforms, 1, 1])
        new_test_shape = self.test_x.shape * np.array([int(keep) + n_transforms, 1, 1])

        # apply transforms to train and test data
        new_train_x = np.empty(new_train_shape, dtype=np.uint8)
        new_test_x = np.empty(new_test_shape, dtype=np.uint8)
        if keep:
            new_train_x[:n_train] = self.train_x
            new_test_x[:n_test] = self.test_x
        for i, transforms in enumerate(tqdm(self.transforms, desc="Applying transforms"), start=int(keep)):
            for j in range(n_train):
                img = self.train_x[j]
                for transform in transforms:
                    img = transform.apply(img)
                new_train_x[n_train * i + j] = img
            for j in range(n_test):
                img = self.test_x[j]
                for transform in transforms:
                    img = transform.apply(img)
                new_test_x[n_test * i + j] = img

        # save new data
        self.train_x = new_train_x
        self.test_x = new_test_x

        # duplicate labels
        self.train_y = np.tile(self.train_y, int(keep) + n_transforms)
        self.test_y = np.tile(self.test_y, int(keep) + n_transforms)

    def __len__(self):
        return self.train_x.shape[0]

    def __getitem__(self, item):
        return self.train_x[item]

    def _load(self):
        pass

    def resize(self, res=28):
        if res == self.res:
            return
        self.train_x = self._get_resized(self.train_x, res)
        self.test_x = self._get_resized(self.test_x, res)
        self.res = res

    def _get_resized(self, data, resolution):
        inter_down = self.inter_down
        inter_up = self.inter_up

        def rsz(img):
            if resolution != img.shape[0]:
                interpolation = inter_down if resolution < img.shape[0] else inter_up
                img = cv2.resize(img, (resolution, resolution), interpolation=interpolation)
            return img

        num_digits = data.shape[0]
        new_digits = np.empty((num_digits, resolution, resolution))
        resized_images = p_map(rsz, [data[i] for i in range(num_digits)],
                               desc="Resizing images",
                               num_cpus=os.cpu_count())
        for i, img in enumerate(resized_images):
            new_digits[i, :, :] = img

        return new_digits

    def _split(self, digits, labels):
        """
        Split the dataset into train and validation splits.

        :param digits: An array of images
        :param labels: An array of labels
        """
        all_count = digits.shape[0]
        train_count = int(all_count * 0.9)
        indices = np.arange(all_count)
        if self.shuffle:
            np.random.shuffle(indices)
        self.train_x = digits[indices[:train_count]]
        self.train_y = labels[indices[:train_count]]
        self.test_x = digits[indices[train_count:]]
        self.test_y = labels[indices[train_count:]]


class MNIST(CharacterDataset):

    def __init__(self, shuffle=True):
        super().__init__(28, shuffle)

    def _load(self):
        print("Loading MNIST dataset")
        # Load data from https://www.openml.org/d/554
        os.makedirs('datasets/', exist_ok=True)

        x, y = fetch_openml('mnist_784', version=1, return_X_y=True, data_home="datasets/", cache=True)
        x = np.array(x, dtype=np.uint8).reshape((70000, 28, 28))
        y = np.array(y, dtype=int)

        indices = np.arange(70000)
        if self.shuffle:
            np.random.shuffle(indices)

        self.train_x = x[indices[:60000]]
        self.train_y = y[indices[:60000]]
        self.test_x = x[indices[60000:]]
        self.test_y = y[indices[60000:]]

        self.train_indices_by_number = [np.flatnonzero(self.train_y == i) for i in range(0, 10)]
        self.test_indices_by_number = [np.flatnonzero(self.test_y == i) for i in range(0, 10)]
        del x, y

    def get_random(self, digit: int) -> np.ndarray:
        """
        Get a random sample of the given digit.

        :returns: 2D numpy array of 28x28 pixels
        """
        return self.train_x[np.random.choice(self.train_indices_by_number[digit])]

    def get_ordered(self, digit: int, index: int) -> np.ndarray:
        """
        Get a random sample of the given digit.

        :returns: 2D numpy array of 28x28 pixels
        """
        return self.train_x[self.train_indices_by_number[digit][index]]

    @property
    def train(self):
        """
        Returns the random train split (60.000 samples by default) of the MNIST dataset.
        """
        return (self.train_x, self.train_y)

    @property
    def test(self):
        """
        Returns the random test split (10.000 samples by default) of the MNIST dataset.
        """
        return (self.test_x, self.test_y)


class FilteredMNIST(MNIST):

    def __init__(self):
        super().__init__()
        filtered = self.train_y > 0
        self.train_x = self.train_x[filtered]
        self.train_y = self.train_y[filtered]
        filtered = self.test_y > 0
        self.test_x = self.test_x[filtered]
        self.test_y = self.test_y[filtered]
        self.train_indices_by_number = [np.flatnonzero(self.train_y == i) for i in range(1, 10)]
        self.test_indices_by_number = [np.flatnonzero(self.test_y == i) for i in range(1, 10)]

        # Reduce all labels by one
        self.train_y -= 1
        self.test_y -= 1

    def get_random(self, digit: int) -> np.ndarray:
        """
        Get a random sample of the given digit.

        :returns: 2D numpy array of 28x28 pixels
        """
        if digit == 0:
            raise ValueError("FilteredMNIST does not contain any 0 digits!")
        return self.train_x[np.random.choice(self.train_indices_by_number[digit - 1])]


class ClassSeparateMNIST(MNIST):

    def __init__(self):
        super().__init__()
        zeros = self.train_y == 0
        self.train_y[zeros] = CLASS_OUT
        zeros = self.test_y == 0
        self.test_y[zeros] = CLASS_OUT

        filtered = self.train_y > 0
        self.train_y[filtered] += 10
        filtered = self.test_y > 0
        self.test_y[filtered] += 10


class CuratedCharactersDataset(CharacterDataset):
    _default_digit_archive_path = "datasets/curated.tar.gz"
    _default_digit_parent_path = "datasets/"
    _default_digit_path = "datasets/curated/"

    def __init__(
            self,
            digits_path=_default_digit_archive_path,
            resolution=64,
            load_chars=None,
            **kwargs
    ):
        # If no specific list of characters is given, load all by default
        if load_chars is None:
            self.load_chars = list(range(33, 92))
            # Skip char 92 ('\') as it is not in the dataset
            self.load_chars.extend(list(range(93, 127)))
            # load_chars = [ord(c) for c in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ']
        else:
            if isinstance(load_chars, str):
                self.load_chars = [ord(c) for c in load_chars]
            else:
                self.load_chars = load_chars
        if not os.path.exists(digits_path):
            raise FileNotFoundError(digits_path)

        # Extract the dataset if is compressed
        if digits_path.endswith((".zip", ".tar", ".tar.gz")):
            self.digit_path = Path(strip_file_ext(digits_path))
            parent = Path(digits_path).parent
            if not os.path.exists(self.digit_path):
                if digits_path.endswith(".zip"):
                    f_archive = zipfile.ZipFile(digits_path)
                else:
                    f_archive = tarfile.TarFile(digits_path)
                f_archive.extractall(parent)
                f_archive.close()
        else:
            self.digit_path: Path = Path(digits_path)

        # Construct a map of all character paths and their respective label
        self.file_map = {}
        for char in self.load_chars:
            files = os.listdir(self.digit_path / str(char))
            for file in files:
                label = self._get_label(char)
                self.file_map.update({str(self.digit_path / str(char) / file): label})

        super().__init__(resolution, **kwargs)

    def _load(self):
        """
        Load the Curated Handwritten Character dataset.
        """
        char_count = len(self.file_map)

        digits = np.empty((char_count, self.res, self.res), dtype=np.uint8)
        labels = np.empty(char_count, dtype=int)

        for i, (path, label) in tqdm(enumerate(self.file_map.items()), total=char_count, desc="Loading images"):
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if self.res != img.shape[0]:
                interpolation = cv2.INTER_LANCZOS4 if self.res < img.shape[0] else cv2.INTER_CUBIC
                digits[i] = cv2.resize(img, (self.res, self.res), interpolation=interpolation)
            else:
                digits[i] = img
            labels[i] = label

        self._split(digits, labels)


class ClassSeparateCuratedCharactersDataset(CuratedCharactersDataset):
    """
    A variant of the CuratedCharactersDataset which assigns the classes 11-19 to digits.
    """
    _digit_offset = 10


class PrerenderedDigitDataset(CharacterDataset):
    default_digit_parent = "datasets/"
    default_digit_path = "datasets/digits/"

    def __init__(self, digits_path="datasets/digits.zip", resolution=128, digit_count=915):
        if not os.path.exists(digits_path):
            raise FileNotFoundError(digits_path)

        self.digit_count = digit_count
        if digits_path.endswith(".zip"):
            parent = Path(digits_path).parent
            self.digit_path = Path(digits_path.rstrip(".zip"))
            if not os.path.exists(self.digit_path):
                with zipfile.ZipFile(digits_path) as f_zip:
                    f_zip.extractall(parent)
        else:
            self.digit_path: Path = Path(digits_path)

        super().__init__(resolution)

    def _load(self):
        digit_count = 9 * self.digit_count
        digits = np.empty((digit_count, self.res, self.res), dtype=np.uint8)
        labels = np.empty(digit_count, dtype=int)

        for i in trange(digit_count, desc="Loading images"):
            digit_path = self.digit_path / f"{i}.png"
            img = cv2.imread(str(digit_path), cv2.IMREAD_GRAYSCALE)
            if self.res != img.shape[0]:
                interpolation = cv2.INTER_LANCZOS4 if self.res < img.shape[0] else cv2.INTER_CUBIC
                digits[i] = cv2.resize(img, (self.res, self.res), interpolation=interpolation)
            else:
                digits[i] = img
            labels[i] = np.floor(i / self.digit_count)

        self._split(digits, labels)


class ConcatDataset(CharacterDataset):
    r"""Concatenate multiple datasets into a single one. Old datasets should be removed afterwards.
    """

    def __init__(self, datasets: List[CharacterDataset], delete=True):
        assert len(datasets) > 0, 'datasets should not be an empty iterable'
        train_size, test_size = 0, 0
        res = None
        for d in datasets:
            if res is None:
                res = d.res
            else:
                d.resize(res)
            train_size += d.train_x.shape[0]
            test_size += d.test_x.shape[0]
        super(ConcatDataset, self).__init__(res)

        self.train_x: np.ndarray = np.empty((train_size, res, res), dtype=np.uint8)
        self.train_y: np.ndarray = np.empty(train_size, dtype=int)
        self.test_x: np.ndarray = np.empty((train_size, res, res), dtype=np.uint8)
        self.test_y: np.ndarray = np.empty(train_size, dtype=int)

        train_offset = 0
        test_offset = 0
        for d in datasets:
            train_size = d.train_x.shape[0]
            test_size = d.test_x.shape[0]
            self.train_x[train_offset:train_offset + train_size] = d.train_x
            self.train_y[train_offset:train_offset + train_size] = d.train_y
            self.test_x[test_offset:test_offset + test_size] = d.test_x
            self.test_y[test_offset:test_offset + test_size] = d.test_y
            train_offset += train_size
            test_offset += test_size
            if delete:
                del d


class DigitDataGenerator(keras.utils.Sequence):

    def __init__(
            self,
            dataset: CharacterDataset,
            batch_size=32,
            shuffle=True,
            **kwargs
    ):
        """Initialization"""
        self.dataset = dataset
        self.batch_size = batch_size
        self.shuffle = shuffle

        self.machine_indices = np.arange(len(self.dataset))
        if self.shuffle:
            np.random.shuffle(self.machine_indices)

    def __len__(self):
        """Denotes the number of batches per epoch"""
        return int(np.floor(len(self.dataset) / self.batch_size))

    def __getitem__(self, index):
        """Generate one batch of data"""
        # Generate indexes of the batch
        indices = self.machine_indices[index * self.batch_size:(index + 1) * self.batch_size]

        # Generate data
        x, y = self.__data_generation(indices)
        x = x.astype(np.float32)

        return x[:, :, :, np.newaxis], y

    def on_epoch_end(self):
        """Updates indexes after each epoch"""
        self.machine_indices = np.arange(len(self.dataset))
        if self.shuffle:
            np.random.shuffle(self.machine_indices)

    def __data_generation(self, indices):
        """Generates data containing batch_size samples"""
        x = self.dataset.train_x[indices]
        y = self.dataset.train_y[indices]

        return x, keras.utils.to_categorical(y, num_classes=9)


class BalancedDataGenerator:
    def __init__(
            self,
            machine_digits: CharacterDataset,
            handwritten_digits: CharacterDataset,
            out_dataset: CharacterDataset,
            batch_size=32,
            shuffle=True,
            flatten=False,
            resolution=28
    ):
        self.machine_dataset = machine_digits
        self.handwritten_dataset = handwritten_digits
        self.out_dataset = out_dataset

        self.shuffle = shuffle
        self.flatten = flatten
        self.resolution = resolution
        self.batch_size = batch_size
        if self.batch_size % 3 != 0:
            warnings.warn("The batch size should be divisible by three!")

        self.num_classes = 20

        self.machine_indices = np.arange(self.machine_dataset.train_y.shape[0])
        self.handwritten_indices = np.arange(self.handwritten_dataset.train_y.shape[0])
        self.out_indices = np.arange(self.out_dataset.train_y.shape[0])

        if self.shuffle:
            np.random.shuffle(self.machine_indices)
            np.random.shuffle(self.handwritten_indices)

    def __len__(self):
        """Denotes the number of batches per epoch"""
        return int(np.ceil(len(self.machine_dataset) * 2 / self.batch_size))

    def __getitem__(self, index):
        """
        Generate one batch of data
        :param index: The batch number.
        :return: Returns a tuple of a 4-dimensional ndarray and the class-categorical label ndarray
        """
        # Generate indexes of the batch
        mini_batch_size = int(self.batch_size / 3)
        mini_batch_size_last = self.batch_size - 2 * mini_batch_size

        machine_indices = self.machine_indices[index * mini_batch_size:(index + 1) * mini_batch_size]
        handwritten_indices = self.handwritten_indices[index * mini_batch_size:(index + 1) * mini_batch_size]
        out_indices = self.out_indices[index * mini_batch_size_last:(index + 1) * mini_batch_size_last]

        # Generate data
        xd, yd = self.__machine_data_generation(machine_indices)
        xm, ym = self.__handwritten_data_generation(handwritten_indices)
        xo, yo = self.__out_data_generation(out_indices)

        # Stack data and convert images to float
        x = np.vstack((xd, xm, xo)).astype(np.float32)
        y = np.vstack((yd, ym, yo))

        # Scale x to 0..1
        x /= 255.

        if self.flatten:
            x = x.reshape(-1, self.resolution ** 2)
        else:
            x = x[:, :, :, np.newaxis]

        return x, y

    def on_epoch_end(self):
        self.machine_indices = np.arange(len(self.machine_dataset))
        self.handwritten_indices = np.arange(len(self.handwritten_dataset.train_y))
        if self.shuffle:
            np.random.shuffle(self.machine_indices)
            np.random.shuffle(self.handwritten_indices)

    def __machine_data_generation(self, indices, ):
        """
        Generates data containing batch_size samples. Machine written digits have class <digit>.
        :param indices: The indices to select
        :return: A tuple of a digit array and a class categorical array
        """
        X = self.machine_dataset.train_x[indices]
        y = self.machine_dataset.train_y[indices]

        return X, keras.utils.to_categorical(y, num_classes=self.num_classes)

    def __handwritten_data_generation(self, indices, ):
        """
        Generates data containing batch_size samples. MNIST digits have class <digit> + 9.
        :param indices: The indices to select
        :return: A tuple of a digit array and a class categorical array
        """
        X = self.handwritten_dataset.train_x[indices]
        y = self.handwritten_dataset.train_y[indices]

        return X, keras.utils.to_categorical(y, num_classes=self.num_classes)

    def __out_data_generation(self, indices, ):
        """
        Generates data containing batch_size samples. MNIST digits have class <digit> + 9.
        :param indices: The indices to select
        :return: A tuple of a digit array and a class categorical array
        """
        X = self.out_dataset.train_x[indices]
        y = self.out_dataset.train_y[indices]

        return X, keras.utils.to_categorical(y, num_classes=self.num_classes)


def generate_composition():
    transform = RandomPerspectiveTransform()
    images = [[] for _ in range(9)]
    for i in range(0, 9):
        img = cv2.imread(f"datasets/digits/{i * 917}.png", cv2.IMREAD_GRAYSCALE)
        img = cv2.rectangle(img, (16, 16), (112, 112), (255, 255, 255), 2)
        images[i].append(img)
        for _ in range(4):
            digit = transform.apply(img)
            images[i].append(digit)
    imgs = np.hstack([np.vstack(digits) for digits in images])
    imgs = cv2.bitwise_not(imgs)
    imgs.save("composition.png")
    plt.imshow(imgs, cmap="gray")
    plt.axis('off')
    plt.show()


def test_generator():
    prerendered_dataset = PrerenderedDigitDataset(digits_path="../datasets/digits/")
    prerendered_dataset.add_transforms(RandomPerspectiveTransform())
    # dataset.add_transforms(RandomPerspectiveTransformX())
    # dataset.add_transforms(RandomPerspectiveTransformY())
    prerendered_dataset.apply_transforms(keep=False)
    prerendered_dataset.resize(28)

    # handwritten non-digits
    curated_out = CuratedCharactersDataset(
        digits_path="../datasets/curated/",
        load_chars="0abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.!?"
    )
    curated_out.add_transforms(RandomPerspectiveTransform())
    curated_out.apply_transforms(keep=False)
    curated_out.resize(28)

    # handwritten digits
    curated_digits = CuratedCharactersDataset(digits_path="../datasets/curated/", load_chars="123456789")
    curated_digits.add_transforms(RandomPerspectiveTransform())
    curated_digits.apply_transforms(keep=False)
    curated_digits.resize(28)

    # mnist digits
    mnist = ClassSeparateMNIST()
    concat_dataset = ConcatDataset([mnist, curated_digits])

    batch_size = 12
    d = BalancedDataGenerator(
        prerendered_dataset, concat_dataset, curated_out,
        batch_size=batch_size,
        shuffle=True,
        resolution=28
    )
    img_l = []
    for i in range(batch_size):
        X, y = d[i]
        img_l.append(np.hstack([img for img in X.squeeze()]))
    plt.figure(figsize=(4, 4))
    plt.imshow(np.vstack(img_l), cmap="gray")
    plt.axis('off')
    plt.show()


def transform_sudoku():
    transform = RandomPerspectiveTransform()
    img = cv2.imread(f"../sudoku.jpeg", cv2.IMREAD_GRAYSCALE)
    transformed = transform.apply(img)
    plt.imshow(transformed, cmap="gray")
    plt.axis('off')
    plt.show()


if __name__ == '__main__':
    # transform_sudoku()
    test_generator()
    # generate_composition()
