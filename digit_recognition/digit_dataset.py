import os
import zipfile

import PIL
import imageio
import keras
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from tqdm import trange

DEBUG = False
DIGIT_COUNT = 915
DIGIT_RESOLUTION = 128


class DigitDataset:

    def __init__(self, digits_path="digits/"):
        if not os.path.exists(digits_path):
            raise FileNotFoundError(digits_path)

        if digits_path.endswith(".zip"):
            self.digit_path = "digits/"
            if not os.path.exists("digits/") or len(os.listdir("digits")) < 9 * DIGIT_COUNT:
                with zipfile.ZipFile(digits_path) as f_zip:
                    f_zip.extractall()
        else:
            self.digit_path = digits_path

        self.digits = np.empty((9 * DIGIT_COUNT, DIGIT_RESOLUTION, DIGIT_RESOLUTION), dtype=np.uint8)
        for i in trange(9 * DIGIT_COUNT, desc="Loading images"):
            digit_path = f"digits/{i}.png"
            self.digits[i] = imageio.imread(digit_path)

        if DEBUG:
            numbers = np.hstack(
                [np.vstack([self.digits[i] for i in range(o, DIGIT_COUNT * 9, 915)]) for o in range(9)])
            plt.imshow(numbers, cmap="gray")
            plt.axis('off')
            plt.show()

    def __len__(self):
        return self.digits.shape[0]

    def __getitem__(self, item):
        return self.digits[item]

    def get_label(self, item):
        if 0 > item >= DIGIT_COUNT * 9:
            raise IndexError
        return np.floor(item / DIGIT_COUNT)


class DigitDataGenerator(keras.utils.Sequence):
    def __init__(self, dataset: DigitDataset = None, batch_size=32, shuffle=True):
        """Initialization"""
        if dataset is not None:
            self.dataset = dataset
        else:
            self.dataset = DigitDataset()
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.on_epoch_end()

    def __len__(self):
        """Denotes the number of batches per epoch"""
        return int(np.floor(len(self.dataset) / self.batch_size))

    def __getitem__(self, index):
        """Generate one batch of data"""
        # Generate indexes of the batch
        indices = self.indices[index * self.batch_size:(index + 1) * self.batch_size]

        # Generate data
        X, y = self.__data_generation(indices)

        return X, y

    def on_epoch_end(self):
        'Updates indexes after each epoch'
        self.indices = np.arange(len(self.dataset))
        if self.shuffle == True:
            np.random.shuffle(self.indices)

    def __data_generation(self, indices):
        'Generates data containing batch_size samples'  # X : (n_samples, *dim, n_channels)
        # Initialization
        X = np.empty((self.batch_size, DIGIT_RESOLUTION, DIGIT_RESOLUTION), dtype=np.uint8)
        y = np.empty((self.batch_size), dtype=int)

        # Generate data
        for i, index in enumerate(indices):
            # Store sample
            digit: np.ndarray = self.dataset[index]
            pos = np.random.randint(0, 33, 8)
            transform = [(pos[0], pos[1]), (128 - pos[2], pos[3]), (128 - pos[4], 128 - pos[5]), (pos[6], 128 - pos[7])]
            # transform = [(32, 0), (128, 0), (128 - 16, 128), (0, 112)]
            digit = self.perspective_transform(digit, transform)
            X[i] = digit

            # Store class
            y[i] = self.dataset.get_label(index)

        return X, keras.utils.to_categorical(y, num_classes=9)

    @staticmethod
    def perspective_transform(arr: np.ndarray, transform):
        x_dim, y_dim = arr.shape
        coeffs = DigitDataGenerator.find_coeffs(transform, x_dim, y_dim)
        arr = np.array(
            Image.fromarray(arr, mode="L").transform(
                (x_dim, y_dim),
                Image.PERSPECTIVE, coeffs,
                Image.BICUBIC
            )
        )
        return arr

    @staticmethod
    def find_coeffs(pa, x_dim=128, y_dim=128):
        """
        Maps the image with its corner points at pa back to their origin and thus making a perspective transform.
        Point order: TL, TR, BR, BL
        Changing the origin
        https://stackoverflow.com/a/14178717
        """
        pb = [(0, 0), (x_dim, 0), (x_dim, y_dim), (0, y_dim)]
        matrix = []
        for p1, p2 in zip(pa, pb):
            matrix.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0] * p1[0], -p2[0] * p1[1]])
            matrix.append([0, 0, 0, p1[0], p1[1], 1, -p2[1] * p1[0], -p2[1] * p1[1]])

        A = np.matrix(matrix, dtype=np.float)
        B = np.array(pb).reshape(8)

        res = np.dot(np.linalg.inv(A.T * A) * A.T, B)
        return np.array(res).reshape(8)


def generate_composition():
    images = [[] for _ in range(9)]
    for i in range(0, 9):
        img = Image.open(f"digits/{i * 917}.png")
        images[i].append(np.array(img))
        d = PIL.ImageDraw.Draw(img)
        d.rectangle([(16, 16), (112, 112)], outline="white")
        del d
        for _ in range(4):
            offsets = np.random.randint(0, 33, 8) * np.array([1, 1, -1, 1, -1, -1, 1, -1])
            transform = [(offsets[0], offsets[1]), (128 + offsets[2], offsets[3]), (128 + offsets[4], 128 + offsets[5]),
                         (offsets[6], 128 + offsets[7])]
            digit = DigitDataGenerator.perspective_transform(np.array(img), transform)
            images[i].append(digit)
    imgs = np.hstack([np.vstack(digits) for digits in images])
    print(imgs.shape)
    ImageOps.invert(Image.fromarray(imgs)).save("composition.png")
    plt.imshow(imgs, cmap="gray")
    plt.axis('off')
    plt.show()


def test_generator():
    pass
    # d = DigitDataGenerator(batch_size=1, shuffle=False)
    # X, y = d.__getitem__(0)
    # plt.imshow(np.hstack([img for img in X]), cmap="gray")
    # plt.axis('off')
    # print(y)
    # plt.show()


# test_generator()
# generate_composition()

def transform_sudoku():
    img: Image.Image = Image.open(f"../sudoku_0.7_0.4.png")
    img = img.convert("L")
    x_dim, y_dim = img.size
    offsets = np.random.randint(0, 33, 8) * np.array([1, 1, -1, 1, -1, -1, 1, -1])
    transform = [(offsets[0], offsets[1]), (x_dim + offsets[2], offsets[3]), (x_dim + offsets[4], y_dim + offsets[5]),
                 (offsets[6], y_dim + offsets[7])]
    transformed = DigitDataGenerator.perspective_transform(np.array(img), transform)
    Image.fromarray(transformed).save("transformed.png")
    plt.imshow(transformed, cmap="gray")
    plt.axis('off')
    plt.show()


transform_sudoku()
