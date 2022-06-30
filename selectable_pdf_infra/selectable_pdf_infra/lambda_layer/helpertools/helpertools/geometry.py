'''
'''
from typing import Dict, Optional

# classes
# -------
class BoundingBox():
    '''
    Class to manipulate a bounding box (bbox). A bounding box is a rectangle aligned with 
    the coordinate system. The bounding box are defined on coordinate system with x 
    pointing toward east and y pointing toward north. This is the usual coordinate 
    system used in euclidian geometry (i.e. lower left origin). Note that images 
    generally have a a cordinate system defined with a upper left origin. 
    '''
    # constructors
    def __init__(self, left: float, bottom: float, right: float, top: float) -> None:
        '''
        constructor.
        '''
        self.bounds = [left, bottom, right, top]
        
    @classmethod
    def from_textract_bbox(cls, textract_bbox: Dict[str, float]) -> None:
        '''
        Construct a BoundingBox object from the bounding box defined by an AWS Textract 
        output json. As Textract uses a coordinate system with a upper left origin 
        (i.e. y pointing downward), the definition of bottom=top+height (note 
        the "+", instead of a "-").
        '''
        return cls(
            left=textract_bbox['Left'],
            bottom=textract_bbox['Top']+textract_bbox['Height'],
            right=textract_bbox['Left']+textract_bbox['Width'],
            top=textract_bbox['Top'],
        )

    # class methods
    def scale(self, x_scale: None, y_scale: Optional[float]=None) -> None:
        '''
        Scale a bounding box by a  x and y factor. If y is not defined, the bbox is 
        scaled by x in all directions
        '''
        if not y_scale:
            y_scale = x_scale
        self.bounds[0] *= x_scale
        self.bounds[1] *= y_scale
        self.bounds[2] *= x_scale
        self.bounds[3] *= y_scale

    # overload methods
    def __getitem__(self, key):
        return self.bounds[key]

    def __setitem__(self, key, value):
        self.bounds[key] = value

    # getters
    @property
    def left(self) -> float:
        return self.bounds[0]

    @property
    def bottom(self) -> float:
        return self.bounds[1]

    @property
    def right(self) -> float:
        return self.bounds[2]

    @property
    def top(self) -> float:
        return self.bounds[3]

    @property
    def width(self) -> float:
        return abs(self.bounds[0]-self.bounds[2])

    @property
    def height(self) -> float:
        return abs(self.bounds[3]-self.bounds[1])