from typing import *

import cv2
import numpy as np

from simulation.transforms.base import ImageTransform


class Filter(ImageTransform):
    def __init__(self, iterations):
        """
        Base class for all filtering operations.

        :param iterations: The number of iterations.
        :type iterations: int
        """
        self.iterations = iterations
        self.kernel = np.array([[0, 0, 0, 0, 0],
                                [0, 0, 0, 0, 0],
                                [0, 0, 1, 0, 0],
                                [0, 0, 0, 0, 0],
                                [0, 0, 0, 0, 0]], dtype=np.float)

    def apply(self, img: np.ndarray) -> np.ndarray:
        """
        Apply the transformation to the input image for *iteration* number of times.

        :param img: The input image, as a numpy array.
        :type img: np.ndarray
        :return: A new ndarray containing the transformed image.
        :rtype: np.ndarray
        """
        for _ in range(self.iterations):
            img = cv2.filter2D(img.astype(np.float), -1, self.kernel)
        return img.astype(np.uint8)


class BoxBlur(Filter):
    def __init__(self, ksize=3, iterations=1):
        """
        Applies box blur.

        :param ksize: The kernel size.
        :type ksize: int
        :param iterations: The number of iterations.
        :type iterations: int
        """
        super().__init__(iterations)
        self.ksize = ksize if isinstance(ksize, tuple) else (ksize, ksize)

    def apply(self, img: np.ndarray) -> np.ndarray:
        for _ in range(self.iterations):
            img = cv2.blur(img, self.ksize)
        return img


class GaussianBlur(Filter):
    def __init__(self, ksize: Union[int, tuple] = 3, sigma=0, iterations=1):
        """
        Applies Gaussian blur.

        :param ksize: The kernel size, must be odd.
        :type ksize: Union[int, tuple]
        :param sigma: The standard deviation of the Gaussian in both x and y direction.
        :type sigma: float
        :param iterations: The number of iterations.
        :type iterations: int
        """
        super().__init__(iterations)
        self.ksize = ksize if isinstance(ksize, tuple) else (ksize, ksize)
        self.sigma = sigma

    def apply(self, img: np.ndarray) -> np.ndarray:
        for _ in range(self.iterations):
            img = cv2.GaussianBlur(img, self.ksize, self.sigma)
        return img


class Dilate(Filter):
    def __init__(self, shape=cv2.MORPH_ELLIPSE, size=(3, 3), iterations=1):
        """
        Dilate the image using a gaussian kernel as structural element.

        :param shape: The OpenCV dilation morphing shape to use.
        :type shape: int
        :param size: The size of the structural element kernel.
        :type size: Tuple[int, int]
        :param iterations: The number of iterations.
        :type iterations: int
        """
        super().__init__(iterations)
        self.kernel = cv2.getStructuringElement(shape, size)
        self.iterations = iterations

    def apply(self, img: np.ndarray) -> np.ndarray:
        return cv2.dilate(img, self.kernel, iterations=self.iterations)


class DilateSoft(Filter):
    def __init__(self, size=(3, 3), iterations=1):
        """
        Dilate the image using a Gaussian kernel as structural element.

        :param size: Size of the Gaussian.
        :type size: tuple[int, int]
        :param iterations: The number of iterations.
        :type iterations: int
        """
        super().__init__(iterations)
        self.kernel = cv2.getGaussianKernel(size, 0)
        self.iterations = iterations

    def apply(self, img: np.ndarray) -> np.ndarray:
        return cv2.dilate(img, self.kernel, iterations=self.iterations)


class SharpenFilter(Filter):
    def __init__(self, iterations=1):
        """
        Applies a 3x3 sharpening filter.

        :param iterations: The number of iterations.
        :type iterations: int
        """
        super().__init__(iterations)
        self.kernel = np.array([[0, -1, 0],
                                [-1, 5, -1],
                                [0, -1, 0]], dtype=np.float)


class ReliefFilter(Filter):
    def __init__(self, iterations=1):
        """
        Applies a 3x3 relief filter.

        :param iterations: The number of iterations.
        :type iterations: int
        """
        super().__init__(iterations)
        self.kernel = np.array([[-2, -1, 0],
                                [-1, 1, 1],
                                [0, 1, 2]], dtype=np.float)


class EdgeFilter(Filter):
    def __init__(self, iterations=1):
        """
        Applies a 3x3 edge detection filter.

        :param iterations: The number of iterations.
        :type iterations: int
        """
        super().__init__(iterations)
        self.kernel = 1 / 4. * np.array([[1, 2, 1],
                                         [2, -12, 2],
                                         [1, 2, 1]], dtype=np.float)


class UnsharpMaskingFilter3x3(Filter):
    def __init__(self, iterations=1):
        """
        Applies a 3x3 unsharp masking filter.

        :param iterations: The number of iterations.
        :type iterations: int
        """
        super().__init__(iterations)
        self.kernel = 1 / 16. * np.array([[-1, -2, -1],
                                          [-2, 28, -2],
                                          [-1, -2, -1]], dtype=np.float)


class UnsharpMaskingFilter5x5(Filter):
    def __init__(self, iterations=1):
        """
        Applies a 5x5 unsharp masking filter.

        :param iterations: The number of iterations.
        :type iterations: int
        """
        super().__init__(iterations)
        self.kernel = 1 / 256. * np.array([[-1., -4., -6., -4., -1],
                                           [-4., -16, -24, -16, -4],
                                           [-6., -24, 476, -24, -6],
                                           [-4., -16, -24, -16, -4],
                                           [-1., -4., -6., -4., -1]], dtype=np.float)