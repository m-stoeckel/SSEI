from typing import List

import numpy as np

from sudoku_generator import Sudoku, SudokuGenerator


class Transform:
    def apply(self, sudoku: Sudoku) -> List[Sudoku]:
        pass


class Rotation(Transform):
    def apply(self, sudoku: Sudoku) -> List[Sudoku]:
        ret: List[Sudoku] = []
        for i in range(3):
            sudoku_from_array = Sudoku.from_array(np.rot90(ret[i].data))
            if sudoku_from_array.is_valid:
                ret.append(sudoku_from_array)
        return ret


class Flip(Transform):
    def apply(self, sudoku: Sudoku) -> List[Sudoku]:
        ret: List[Sudoku] = []

        for ax in [0, 1, None]:
            sudoku_from_array = Sudoku.from_array(np.flip(sudoku.data, ax))
            if sudoku_from_array.is_valid:
                ret.append(sudoku_from_array)
            return ret


class MajorSwitch(Transform):
    def __init__(self, column_switch=(0, 1, 2), row_switch=(0, 1, 2), column_first=False):
        lookup = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
        if not set(column_switch) == set(row_switch) == {0, 1, 2}:
            raise ValueError()

        self.column_order = [n for cid in column_switch for n in lookup[cid]]
        self.row_order = [n for cid in row_switch for n in lookup[cid]]
        self.column_first = column_first

    def apply(self, sudoku: Sudoku) -> List[Sudoku]:
        sudoku_from_array = Sudoku.from_array(sudoku.data.copy())
        if self.column_first:
            sudoku_from_array.data[:, self.column_order] = sudoku.data[:, [0, 1, 2, 3, 4, 5, 6, 7, 8]]
            sudoku_from_array.data[self.row_order, :] = sudoku_from_array.data[[0, 1, 2, 3, 4, 5, 6, 7, 8], :]
        else:
            sudoku_from_array.data[self.row_order, :] = sudoku.data[[0, 1, 2, 3, 4, 5, 6, 7, 8], :]
            sudoku_from_array.data[:, self.column_order] = sudoku_from_array.data[:, [0, 1, 2, 3, 4, 5, 6, 7, 8]]

        if not sudoku_from_array.is_valid:
            print(sudoku_from_array.data)
            raise ValueError
        return [sudoku_from_array]


class TransformSudokuGenerator(SudokuGenerator):
    def __init__(self, n: int, **kwargs):
        super().__init__(n, **kwargs)
        self.transforms: List[Transform] = []

    def add_transform(self, transform: Transform):
        self.transforms.append(transform)

    def build(self):
        for transform in self.transforms:
            newl: List[Sudoku] = []
            for s in self.generated:
                newl.extend(transform.apply(s))
            self.generated.extend(newl)
