from enum import Enum, auto

class ParticipationEnum(Enum):

    def _generate_next_value_(name, start, count, last_values):
        return name.lower()
    
    NO = auto()
    YES = auto()
    LEGGACY = auto()
    AFK = auto()

class CoopStatusEnum(Enum):

    def _generate_next_value_(name, start, count, last_values):
        return name.lower()
    
    RUNNING = False
    COMPLETED = auto()
    FAILED = auto()