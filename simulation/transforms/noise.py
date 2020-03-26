import cv2
import numpy as np

from simulation.render import Color
from simulation.transforms.base import ImageTransform


class UniformNoise(ImageTransform):
    def __init__(self, low=0, high=127):
        super().__init__()
        self.low = low
        self.high = high

    def noise(self, size):
        return np.random.uniform(self.low, self.high, size)

    def apply(self, img: np.ndarray) -> np.ndarray:
        noise = self.noise(img.shape)
        img = img.astype(np.float) + noise
        img = np.clip(img, 0, 255)
        return img


class GaussianNoise(ImageTransform):
    def __init__(self, mu=0, sigma=4):
        super().__init__()
        self.mu = mu
        self.sigma = sigma

    def noise(self, size):
        return np.random.normal(self.mu, self.sigma, size)

    def apply(self, img: np.ndarray) -> np.ndarray:
        noise = self.noise(img.shape)
        img = img.astype(np.float) + noise
        img = np.clip(img, 0, 255)
        return img.astype(np.uint8)


class SpeckleNoise(GaussianNoise):
    """
    :source: https://stackoverflow.com/a/30609854
    """

    def __init__(self, mu=0, sigma=8):
        super().__init__(mu, sigma)
        self.mu /= 255.
        self.sigma /= 255.

    def apply(self, img: np.ndarray) -> np.ndarray:
        noise = self.noise(img.shape)
        img = img.astype(np.float) / 255.
        img = img * noise * 255
        img = np.clip(img, 0, 255)
        return img.astype(np.uint8)


class PoissonNoise(ImageTransform):
    """
    :source: https://stackoverflow.com/a/30609854
    """

    def apply(self, img: np.ndarray) -> np.ndarray:
        img = img.astype(np.float) / 255.
        vals = len(np.unique(img))
        vals = 2 ** np.ceil(np.log2(vals))
        noisy = np.random.poisson(img * vals) / float(vals) * 255
        noisy = np.clip(noisy, 0, 255)
        return noisy.astype(np.uint8)


class SaltAndPepperNoise(ImageTransform):
    """
    :source: https://stackoverflow.com/a/30609854
    """

    def __init__(self, amount=0.02, ratio=0.5):
        """

        :param amount: Salt & pepper amount.
        :type amount:
        :param ratio: Salt vs. pepper ratio.
        :type ratio:
        """
        super().__init__()
        self.amount = amount
        self.ratio = ratio

    def apply(self, img: np.ndarray) -> np.ndarray:
        # Salt mode
        img = img.copy()
        num_salt = int(np.ceil(self.amount * img.size * self.ratio))
        indices = (np.random.choice(np.arange(img.shape[0]), num_salt),
                   np.random.choice(np.arange(img.shape[1]), num_salt))
        img[indices] = 255

        # Pepper mode
        num_pepper = int(np.ceil(self.amount * img.size * (1. - self.ratio)))
        indices = (np.random.choice(np.arange(img.shape[0]), num_pepper),
                   np.random.choice(np.arange(img.shape[1]), num_pepper))
        img[indices] = 0
        return img


class EmbedInGrid(ImageTransform):
    def __init__(self, inset=0.2):
        super().__init__()
        self.inset = inset
        self.offset = inset / 2

    def apply(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            grid_image_shape = (
                int(img.shape[0] + self.inset * img.shape[0]),
                int(img.shape[1] + self.inset * img.shape[1]),
                img.shape[2]
            )
        else:
            grid_image_shape = (
                int(img.shape[0] + self.inset * img.shape[0]),
                int(img.shape[1] + self.inset * img.shape[1]),
            )
        grid_image = np.full(grid_image_shape, 255, dtype=np.uint8)
        offset_x, offset_y = int(self.offset * img.shape[0]), int(self.offset * img.shape[1])
        grid_image[offset_x:offset_x + img.shape[0], offset_y:offset_y + img.shape[1]] = img
        cv2.rectangle(grid_image, (offset_x, offset_y),
                      (grid_image.shape[0] - offset_x, grid_image.shape[1] - offset_y),
                      Color.BLACK.value, thickness=int(img.shape[0] * 0.05))
        return self.random_crop(grid_image, img.shape)

    @staticmethod
    def random_crop(grid_img, shape) -> np.ndarray:
        offset = np.array(grid_img.shape) - np.array(shape)
        offset_x = np.random.randint(0, offset[0])
        offset_y = np.random.randint(0, offset[1])
        return grid_img[offset_x:offset_x + shape[0], offset_y:offset_y + shape[1]]


class JPEGEncode(ImageTransform):
    def __init__(self, quality=80):
        self.quality = quality

    def apply(self, img: np.ndarray) -> np.ndarray:
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
        result, encimg = cv2.imencode('.jpg', img, encode_param)
        decimg = cv2.imdecode(encimg, cv2.IMREAD_GRAYSCALE)
        return decimg
