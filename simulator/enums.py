from enum import Enum


class Gender(Enum):
    MALE = 0
    FEMALE = 1


class AgeGroup(Enum):
    KID = 12
    '''below 12 years'''

    TEENAGE = 18
    '''12-17 years'''

    YOUNG_ADULT = 45
    '''18-44 years'''

    MIDDLE_ADULT = 65
    '''45-64 years'''

    OLDER_ADULT = 100
    '''65 years and older'''


class FamilyStatus(Enum):
    SINGLE = 1
    PARENT = 2
    CHILD = 3


class PaymentMethod(Enum):
    CASH = 1
    DIGITAL_CASH = 2
    DEBIT_CARD = 3
    CREDIT_CARD = 4


class OrderStatus(Enum):
    COLLECTING = 1
    QUEUING = 2
    PROCESSING = 3
    WAITING_PAYMENT = 4
    DOING_PAYMENT = 5
    PAID = 6
    DONE = 7


class EmployeeAttendanceStatus(Enum):
    OUT_OF_OFFICE = 0
    BEGIN_SHIFT = 0
    COMPLETE_SHIFT = 0


class EmployeeShift(Enum):
    NONE = 0
    FIRST = 1
    SECOND = 2


class EmployeeStatus(Enum):
    OFF = 1
    OUT_OF_OFFICE = 2
    STARTING_SHIFT = 3
    IDLE = 4
    PROCESSING_ORDER = 5
