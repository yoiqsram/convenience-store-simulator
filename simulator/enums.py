from enum import Enum


class Gender(Enum):
    MALE = 0
    FEMALE = 1


class AgeGroup():
    kid = 0
    '''below 12 years'''

    teenage = 1
    '''12-18 years'''

    young_adult = 2
    '''19-44 years'''

    middle_adult = 3
    '''45-64 years'''

    older_adult = 4
    '''65 years and older'''


class PaymentMethod(Enum):
    CASH = 0
    DIGITAL_CASH = 1
    DEBIT_CARD = 2
    CREDIT_CARD = 3
