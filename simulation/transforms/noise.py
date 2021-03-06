from abc import abstractmethod, ABCMeta
from typing import Union, Tuple

import cv2
import numpy as np

from simulation import Color
from simulation.transforms import ImageTransform


class SimpleNoise(ImageTransform, metaclass=ABCMeta):
    @abstractmethod
    def noise(self, shape: tuple):
        """
        Returns the noise as an numpy array of the given shape.

        Args:
            shape(tuple): The shape of the noise.

        Returns:
          :py:class:`numpy.ndarray`: A numpy array with noise values.

        """
        pass


class UniformNoise(SimpleNoise):
    """
    Adds uniform noise (additive) to input images.
    
    The noise is drawn from an float uniform distribution. The image is cast to float and clipped to uint8 after the
    noise was added.

    """

    def __init__(self, low=-16, high=16):
        """
        

        Args:
            low(float, optional): Lower bound of the uniform distribution. (Default value = -16)
            high(float, optional): Upper bound of the uniform distribution. (Default value = 16)

        """
        super().__init__()
        self.low = low
        self.high = high

    def noise(self, shape: tuple):
        return np.random.uniform(self.low, self.high, shape)

    def apply(self, img: np.ndarray) -> np.ndarray:
        noise = self.noise(img.shape)
        img = img.astype(np.float) + noise
        img = np.clip(img, 0, 255)
        return img


class GaussianNoise(SimpleNoise):
    """
    Adds Gaussian noise (additive) to input images.
    
    Noise is drawn from a float Gaussian normal. The image is cast to float and clipped to uint8 after the noise
    was added.

    """

    def __init__(self, mu=0.0, sigma=4.0):
        """
        

        Args:
            mu(float, optional): The mean of the Gaussian. (Default value = 0.0)
            sigma(float, optional): The standard deviation of the Gaussian. (Default value = 4.0)

        """
        super().__init__()
        self.mu = mu
        self.sigma = sigma

    def noise(self, shape: tuple):
        return np.random.normal(self.mu, self.sigma, shape)

    def apply(self, img: np.ndarray) -> np.ndarray:
        noise = self.noise(img.shape)
        img = img.astype(np.float) + noise
        img = np.clip(img, 0, 255)
        return img.astype(np.uint8)


class SpeckleNoise(GaussianNoise):
    """
    Adds Gaussian noise (multiplicative) to input images.
    
    Noise is drawn from a float Gaussian normal. The image is cast to float and clipped to uint8 after the noise
    was added.

    """

    def __init__(self, mu=0., sigma=4.0):
        """
        

        Args:
            mu(float, optional): The mean of the Gaussian. (Default value = 0.)
            sigma(float, optional): The standard deviation of the Gaussian. (Default value = 4.0)

        """
        super().__init__(mu, sigma)
        self.mu /= 255.
        self.sigma /= 255.

    def apply(self, img: np.ndarray) -> np.ndarray:
        noise = self.noise(img.shape)
        img = img.astype(np.float)
        img += img * noise
        img = np.clip(img, 0, 255)
        return img.astype(np.uint8)


class PoissonNoise(ImageTransform):
    """
    Adds data dependent poisson noise to input images.
    
    :sources: https://stackoverflow.com/a/30609854

    """

    def apply(self, img: np.ndarray) -> np.ndarray:
        img = img.astype(np.float) / 255.
        noise = 2 ** np.ceil(np.log2(len(np.unique(img))))
        noisy = np.random.poisson(img * noise) / float(noise) * 255
        noisy = np.clip(noisy, 0, 255)
        return noisy.astype(np.uint8)


class SaltAndPepperNoise(ImageTransform):
    """Sets random single pixels to black or white white."""

    def __init__(self, amount: Union[int, float] = 0.01, ratio=0.5):
        """
        :sources: https://stackoverflow.com/a/30609854

        Args:
          amount(float): Salt & pepper amount.
          ratio(float, optional): Salt vs. pepper ratio. (Default value = 0.5)

        """
        super().__init__()
        self.amount = amount
        self.ratio = ratio

    def apply(self, img: np.ndarray) -> np.ndarray:
        # Salt mode
        img = img.copy()
        if isinstance(self.amount, float) or self.amount < 1:
            num_salt = int(np.ceil(self.amount * img.size * self.ratio))
        else:
            num_salt = int(np.ceil(self.amount * self.ratio))
        indices = (np.random.choice(np.arange(img.shape[0]), num_salt),
                   np.random.choice(np.arange(img.shape[1]), num_salt))
        img[indices] = 255

        if self.ratio == 1.0:
            return img

        # Pepper mode
        if isinstance(self.amount, float) or self.amount < 1:
            num_pepper = int(np.ceil(self.amount * img.size * (1. - self.ratio)))
        else:
            num_pepper = int(np.ceil(self.amount * (1. - self.ratio)))
        indices = (np.random.choice(np.arange(img.shape[0]), num_pepper),
                   np.random.choice(np.arange(img.shape[1]), num_pepper))
        img[indices] = 0
        return img


class GrainNoise(SaltAndPepperNoise):
    """
    A variant of `SaltAndPepperNoise`__ which adds larger white grains by using reshaping, dilation and JPEG encoding
    with zero pepper SaltAndPepperNoise.

    """

    def __init__(self, amount=0.0005, iterations=2, shape=(102, 102)):
        """
        

        Args:
          amount(float, optional): Salt amount. (Default value = 0.0005)
          iterations(int): The number of iterations. (Default value = 2)
          shape(tuple[int, int]): The intermediate scaling shape. (Default value = (102, 102)

        """
        super().__init__(amount, 1)
        self.iterations = iterations
        self.shape = shape

    def apply(self, img: np.ndarray) -> np.ndarray:
        encode = JPEGEncode(90)
        img = img.astype(np.int)
        for _ in range(self.iterations):
            salt = super().apply(np.zeros(self.shape, dtype=np.uint8))
            salt = cv2.dilate(salt, cv2.getStructuringElement(cv2.MORPH_RECT, tuple(np.random.randint(3, 10, 2))))
            salt = cv2.resize(salt, img.shape, interpolation=cv2.INTER_AREA)
            salt = encode.apply(salt)
            img += salt.astype(np.int)
        return np.clip(img, 0, 255).astype(np.uint8)


class EmbedInRectangle(ImageTransform):
    """
    Embeds images in a white rectangle.
    
    The given image is inserted into the center of a new, empty image with the given :py:attr:`inset`.
    Then, a rectangle is drawn at the half the :py:attr:`inset` distance to the border. Finally, the a random crop to
    the original image shape is performed and the new image is returned.

    """

    def __init__(self, inset=0.1, thickness=1):
        """
        

        Args:
            inset(float, optional): The distance to inset the processed image by, in percent. (Default value = 0.1)
            thickness(int, optional): The thickness of the rectangle. (Default value = 1)

        """
        super().__init__()
        self.inset = inset
        self.offset = inset / 2
        self.thickness = thickness

    def apply(self, img: np.ndarray) -> np.ndarray:
        grid_image, offset_x, offset_y = self.expand_image(img)

        grid_image[offset_x:offset_x + img.shape[0], offset_y:offset_y + img.shape[1]] = img
        cv2.rectangle(grid_image, (offset_x, offset_y),
                      (grid_image.shape[0] - offset_x - 1, grid_image.shape[1] - offset_y - 1),
                      Color.WHITE.value, thickness=self.thickness)

        if self.inset > 0:
            return self.random_crop(grid_image, img.shape)
        else:
            return grid_image

    def expand_image(self, img):
        """
        Get the expanded image on which the grid is drawn where the original image is in the center.

        Args:
            img: The image to be expanded.

        Returns:
            The expanded image.

        """
        if self.inset > 0:
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
        else:
            grid_image_shape = img.shape

        grid_image = np.full(grid_image_shape, 0, dtype=np.uint8)
        offset_x, offset_y = int(abs(self.offset * img.shape[0])), int(abs(self.offset * img.shape[1]))

        if self.inset > 0:
            grid_image[offset_x:offset_x + img.shape[0], offset_y:offset_y + img.shape[1]] = img
        else:
            grid_image = img.copy()

        return grid_image, offset_x, offset_y

    @staticmethod
    def random_crop(grid_img: np.ndarray, shape: Tuple[int, int]) -> np.ndarray:
        """
        Randomly crops the input image to the given shape.

        Args:
              grid_img(:py:class:`numpy.ndarray`): Input image to be cropped.
              shape(tuple[int, int]): The new shape.

        Returns:
            :py:class:`numpy.ndarray`: The cropped image.

        """
        offset = np.array(grid_img.shape) - np.array(shape)
        offset_x = np.random.randint(0, offset[0])
        offset_y = np.random.randint(0, offset[1])
        return grid_img[offset_x:offset_x + shape[0], offset_y:offset_y + shape[1]]


class EmbedInGrid(EmbedInRectangle):
    """
    Embeds images in a white rectangle.
    
    The given image is inserted into the center of a new, empty image with the given :py:attr:`inset`.
    Then, a rectangle is drawn at the half the :py:attr:`inset` distance to the border. Finally, the a random crop to
    the original image shape is performed and the new image is returned.

    """

    def __init__(self, inset=0.2, thickness=1):
        """
        

        Args:
            inset(float, optional): The distance to inset the processed image by, in percent. (Default value = 0.2)
            thickness(int, optional): The thickness of the grid. (Default value = 1)

        """
        super().__init__(inset, thickness)

    def apply(self, img: np.ndarray) -> np.ndarray:
        grid_image, offset_x, offset_y = self.expand_image(img)

        # Draw grid lines
        cv2.line(grid_image, (offset_x, 0), (offset_x, grid_image.shape[0]), Color.WHITE.value, self.thickness)
        cv2.line(grid_image, (grid_image.shape[0] - offset_x - 1, 0),
                 (grid_image.shape[0] - offset_x - 1, grid_image.shape[0]),
                 Color.WHITE.value, self.thickness)
        cv2.line(grid_image, (0, offset_y), (grid_image.shape[1], offset_y), Color.WHITE.value, self.thickness)
        cv2.line(grid_image, (0, grid_image.shape[1] - offset_y - 1),
                 (grid_image.shape[1], grid_image.shape[1] - offset_y - 1),
                 Color.WHITE.value, self.thickness)

        if self.inset > 0:
            return self.random_crop(grid_image, img.shape)
        else:
            return grid_image


class JPEGEncode(ImageTransform):
    """Encode and subsequently decode the input image using the JPEG algorithm with the supplied :py:attr:`quality`."""

    def __init__(self, quality=80):
        """
        

        Args:
            quality(int, optional): The quality parameter for the JPEG algorithm. (Default value = 80)

        """
        self.quality = quality

    def apply(self, img: np.ndarray) -> np.ndarray:
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
        result, encimg = cv2.imencode('.jpg', img, encode_param)
        decimg = cv2.imdecode(encimg, cv2.IMREAD_GRAYSCALE)
        return decimg
