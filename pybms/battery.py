class ProtectionStatus:
    def __init__(self, ):
        self.battery_overvoltage = False
        self.battery_undervoltage = False
        self.charge_overtemp = False
        self.charge_undertemp = False
        self.discharge_overtemp = False
        self.discharge_undertemp = False
        self.charge_overcurrent = False
        self.discharge_overcurrent = False

    @property
    def alarm(self):
        return self.battery_overvoltage or \
        self.battery_undervoltage or \
        self.charge_overtemp or \
        self.charge_undertemp or \
        self.discharge_overtemp or \
        self.discharge_undertemp or \
        self.charge_overcurrent or \
        self.discharge_overcurrent

class Cell:
    def __init__(self, voltage, balance):
        self.voltage = voltage
        self.balance = balance

class Battery:
    def __init__(self, voltage, current, capacity_remaining, capacity, 
                 state_of_charge, string_count,
                 temperatures):
        self.voltage = voltage
        self.current = current
        self.capacity_remaining = capacity_remaining
        self.capacity = capacity
        self.cycles = cycles
        self.state_of_charge = state_of_charge
        self.string_count = string_count

        self.timestamp = None