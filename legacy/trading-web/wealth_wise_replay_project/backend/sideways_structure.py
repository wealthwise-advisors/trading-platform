class SidewaysStructure:
    def __init__(self, start_index, end_index, high_min, high_max, low_min, low_max, num_swings, structure_type):
        self.start_index = start_index
        self.end_index = end_index
        self.high_min = high_min
        self.high_max = high_max
        self.low_min = low_min
        self.low_max = low_max
        self.num_swings = num_swings
        self.structure_type = structure_type

    def __repr__(self):
        return (f"SidewaysStructure(start_index={self.start_index}, end_index={self.end_index}, "
                f"high_min={self.high_min}, high_max={self.high_max}, "
                f"low_min={self.low_min}, low_max={self.low_max}, "
                f"num_swings={self.num_swings}, structure_type='{self.structure_type}')")