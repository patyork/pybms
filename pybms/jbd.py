from enum import Enum
import asyncio
import datetime
from bleak import BleakClient

from . import battery
from . import tools

class JBDProtectionStatus(battery.ProtectionStatus):
    def __init__(self, protection_data):
        self._protection = protection_data
        
        self.monomer_overvoltage = bool(self._protection>>0)
        self.monomer_undervoltage = bool(self._protection>>1)
        self.battery_overvoltage = bool(self._protection>>2)
        self.battery_undervoltage = bool(self._protection>>3)
        self.charge_overtemp = bool(self._protection>>4)
        self.charge_undertemp = bool(self._protection>>5)
        self.discharge_overtemp = bool(self._protection>>6)
        self.discharge_undertemp = bool(self._protection>>7)
        self.charge_overcurrent = bool(self._protection>>8)
        self.discharge_overcurrent = bool(self._protection>>9)
        self.short_circuit = bool(self._protection>>10)
        self.hardware_error = bool(self._protection>>11)
        self.software_switch_lock = bool(self._protection>>12)

    @property
    def alarm(self):
        return super().alarm or \
        \
        self.monomer_overvoltage or \
        self.monomer_undervoltage or \
        self.short_circuit or \
        self.hardware_error or \
        self.software_switch_lock

class JBDBMS:
    READ = "0000ff01-0000-1000-8000-00805f9b34fb"
    WRITE = "0000ff02-0000-1000-8000-00805f9b34fb"
    
    class COMMAND(Enum):
        READ_BASIC = 3
        READ_VOLTAGES = 4
        READ_VERSION = 5
    
    class STATE(Enum):
        IDLE = 0
        AWAIT_BASIC = 1
        AWAIT_VOLTAGES = 2
        AWAIT_VERSION = 3

        FINISH_BASIC = 10
        FINISH_VOLTAGES = 20
        FINISH_VERSION = 30
    
        RETRY = 100
    
    
    def __init__(self, client, response_fn):
        self.bt_client = client
        self.response_fn = response_fn
        self.state = self.STATE.IDLE

        self.buffer = bytes()
        self.buffer_history = []

        self.version = None
        
        return

    async def start(self):
        await self.bt_client.start_notify(self.READ, self.notification_handler)
        await asyncio.sleep(0.2)

    async def stop(self):
        await self.bt_client.stop_notify(self.READ)
        await asyncio.sleep(0.2)

    def checksum(self, bibs):
        return (pow(2,16)-1 - sum(bibs) + 1).to_bytes(2, 'big') # which is: the result of the inverse +1 of the sum of all the

    def generate_command(self, command, data=None):
        command = command.value
        data_section = (command).to_bytes(1, "big")
        if data is None:
            data_section += (0).to_bytes(1, "big")
        
        command = bytes.fromhex("DD A5")
        command += data_section + self.checksum(data_section)
        command += bytes.fromhex("77 ")
        return command

    def process(self, data=None):
        if data is None:
            data = self.buffer
            
        if self.state == self.STATE.FINISH_BASIC:
            data = data[2:-3]
            status = data.pop()
            length = data.pop()
            voltage = data.pop(2)
            current = data.pop(2)
            capacity_remaining = data.pop(2)
            capacity = data.pop(2)
            cycles = data.pop(2)
            manufacture_date = data.pop(2)
            balance = data.pop(4)
            protection = data.pop(2)
            software_version = data.pop()
            soc = data.pop()
            switch_state = data.pop()
            number_strings = data.pop()
            number_ntc = data.pop()
            temperatures = [(data.pop(2)-2731) / 10.0 for i in range(number_ntc)]
            unknown = data.pop(len(data))

            #print(status, length, voltage, current, capacity_remaining, capacity, cycles, manufacture_date, balance, protection, software_version, soc, switch_state, number_strings, number_ntc, temperatures)

            self.response_fn({'BASIC' : (voltage, current, capacity_remaining, capacity, cycles, manufacture_date, balance, 
                protection, software_version, soc, switch_state, number_strings, number_ntc, temperatures, unknown)})

        elif self.state == self.STATE.FINISH_VOLTAGES:
            data = data[2:-3]
            length = data.pop(2)
            voltages = [data.pop(2)/1000.0 for i in range(int(length/2))]

            self.response_fn({'VOLTAGES' : voltages})

            ###print(voltages)

        elif self.state == self.STATE.FINISH_VERSION:
            data = data[2:-3]
            status = data.pop(2)
            self.version = data

            self.response_fn({'VERSION' : self.version})

            #print(data)
        
        self.state = self.STATE.IDLE
        return
    
    def notification_handler(self, characteristic, data):
        #print(data.hex())

        self.buffer += data

        if data[-1] == 0x77: # stop byte
            self.state = self.STATE(self.state.value*10)
            self.buffer = tools.IntBuffer(self.buffer)
            self.buffer_history.append(self.buffer)
            #print("end of file")

    async def wait_for_state(self, target_state):
        counts = 0
        while(True):
            if self.state == target_state: return True

            await asyncio.sleep(0.1)
            counts += 1
            if counts > 25:
                self.state = self.STATE.RETRY
                return False


    async def read_basic(self):
        self.buffer = bytes() # Clear Buffer
        command = self.generate_command(self.COMMAND.READ_BASIC)
        #print(command.hex())
        self.state = self.STATE.AWAIT_BASIC
        await self.bt_client.write_gatt_char(self.WRITE, command, response=False)
        
        if not await self.wait_for_state(self.STATE.FINISH_BASIC):
            print("Failed to read basic information")
            return False

        self.process()
        return True

    async def read_voltages(self):
        self.buffer = bytes() # Clear Buffer
        command = self.generate_command(self.COMMAND.READ_VOLTAGES)
        #print(command.hex())
        self.state = self.STATE.AWAIT_VOLTAGES
        await self.bt_client.write_gatt_char(self.WRITE, command, response=False)
        
        if not await self.wait_for_state(self.STATE.FINISH_VOLTAGES):
            print("Failed to read voltage information")
            return False

        self.process()
        return True

    async def read_version(self, notify_on_error=True):
        self.buffer = bytes() # Clear Buffer
        command = self.generate_command(self.COMMAND.READ_VERSION)
        #print(command.hex())
        self.state = self.STATE.AWAIT_VERSION
        await self.bt_client.write_gatt_char(self.WRITE, command, response=False)
        
        if not await self.wait_for_state(self.STATE.FINISH_VERSION):
            if notify_on_error: print("Failed to read version information")
            return False

        self.process()
        return True



    async def read(self):
        # Read often fails on first attempt
        try:
            await self.read_version(False)
        except:
            self.state = self.STATE.IDLE
            
        if await self.read_basic():
            if await self.read_voltages():
                if await self.read_version():
                    return True

        return False

class JBDBattery:
    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.bt_client = BleakClient(self.mac_address)
        self.bms = JBDBMS(self.bt_client, self.on_data)
        self.timestamp = datetime.datetime.now()
        
        
    @property
    def manufacture_date(self):
        if type(self._manufacture_date) == int:
            return datetime.date(2000 + (self._manufacture_date>>9), (self._manufacture_date>>5) & 0x0f, self._manufacture_date & 0x1f)
            
    @property
    def software_version(self):
        if type(self._software_version) == int:
            return ((self._software_version >> 4) & 0x0f) + ((self._software_version & 0x0f) / 10.0)
            
    @property
    def switch_charge(self):
        if type(self._switch_state) == int:
            return bool(self._switch_state & 0x01)
            
    @property
    def switch_discharge(self):
        if type(self._switch_state) == int:
            return bool(self._switch_state>>1 & 0x01)

    @property
    def balance(self):
        return [bool(self._balance>>i) for i in range( self.string_count )]

    @property
    def protection_status(self):
        if type(self._protection) == int:
            return JBDProtectionStatus(self._protection)

    def on_data(self, data):
        #print(data)
        self.timestamp = datetime.datetime.now()
        if 'BASIC' in data.keys():
            voltage, current, capacity_r, capacity, cycles, manufacture_d, balance, protection, software_v, soc, switch_s, number_s, number_t, temps, unknowns = data['BASIC']
            
            self.voltage = voltage
            self.current = current
            self.capacity_remaining = capacity_r
            self.capacity = capacity
            self.cycles = cycles
            self._manufacture_date = manufacture_d
            self._balance = balance
            self._protection = protection
            self._software_version = software_v
            self.state_of_charge = soc
            self._switch_state = switch_s
            self.string_count = number_s
            self.temperature_count = number_t
            self.temperatures = temps
            ##self.bms_version = bms_version
            self.unknows = unknowns

        elif 'VOLTAGES' in data.keys():
            self.voltages = data['VOLTAGES']
            self.cells = []
            for i in range(self.string_count):
                self.cells.append(battery.Cell(self.voltages[i], self.balance[i]))

        elif 'VERSION' in data.keys():
            self.bms_version = data['VERSION']

    async def read_once(self, retry=1):
        try:
            if not self.bt_client.is_connected:
                await self.bt_client.connect()
            await self.bms.start()
            await self.bms.read()
            await self.bms.stop()
        except:
            print("Retry ", retry)
            if retry > 0:
                await self.read_once(min(retry-1, 3))
        await self.bt_client.disconnect()

