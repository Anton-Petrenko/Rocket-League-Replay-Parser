import json
import struct

class Parser:
    def __init__(self, filename: str):
        self.data = open(filename, "rb").read()
    
    def le_i32(self, d):
        return int.from_bytes(d[:4], byteorder="little", signed=True)

    def advance(self, size):
        self.data = self.data[size:]

    def view_data(self, size):
        if size > len(self.data):
            raise ValueError("Too many bytes requested")
        else:
            return self.data[:size]

    def take(self, size, f):
        res = f(self.view_data(size))
        self.advance(size)
        return res

    def take_bytes(self, size):
        result, tail = self.data[:size], self.data[size:]
        self.data = tail
        return result

    def take_i32(self):
        return self.take(4, self.le_i32)
    
    def take_u32(self):
        return self.take(4, self.le_i32) & 0xFFFFFFFF

    def view_data(self, size):
        if size > len(self.data):
            raise ValueError("Too many bytes requested")
        else:
            return self.data[:size]

    def take_data(self, size):
        res = self.view_data(size)
        self.advance(size)
        return res

    def decode_str(self, input):
        return input[:-1].decode("utf-8")

    def decode_utf16(self, input):
        return input[:-2].decode("utf-16")
    
    def decode_windows1252(self, input):
        return input[:-1].decode("windows-1252")

    def parse_str(self):
        size = self.take(4, self.le_i32)
        data = self.take_data(size)
        return self.decode_str(data)

    def parse_text(self):
        characters = self.take(4, self.le_i32)

        if not -10000 <= characters <= 10000:
            raise TypeError("Too large")
        elif characters < 0:
            size = characters * -2
            data = self.take_data(size)
            return self.decode_utf16(data)
        else:
            data = self.take_data(characters)
            return self.decode_windows1252(data)

    def repeat(self, size, f):
        if size > 25000:
            raise ValueError("List is too large")
        
        res = []
        for i in range(size):
            res.append(f())

        return res

    def array_property(self):
        size = self.take_i32()
        arr = self.repeat(size, self.parse_rdict)
        return arr

    def parse_rdict(self):
        res = {}
        key = self.parse_str()
        while key != 'None':
            kind = self.parse_str()
            _size = self.take_u32()
            _ignored = self.take_data(4)

            if kind == "BoolProperty":
                val = self.take_data(1) == 1
            elif kind == "ByteProperty":
                kind = self.parse_str()
                if kind == "None":
                    self.advance(1)
                    continue
                val = {
                    "kind": kind,
                    "value": self.parse_str()
                }
            elif kind == "ArrayProperty":
                val = self.array_property()
            elif kind == "FloatProperty":
                bytes = self.take_bytes(4)
                val = struct.unpack('<f', bytes)[0]
            elif kind == "IntProperty":
                bytes = self.take_bytes(4)
                val = struct.unpack('<i', bytes)[0]
            elif kind == "NameProperty":
                val = self.parse_text()
            elif kind == "StrProperty":
                val = self.parse_text()
            elif kind == "StructProperty":
                name = self.parse_str()
                fields = self.parse_rdict()
                val = {
                    "name": self.parse_str(),
                }.update(fields)
            elif kind == "QWordProperty":
                bytes = self.take_bytes(8)
                val = struct.unpack('<Q', bytes)[0]
            else:
                ValueError("Value run into that is not accounted for.")
            
            res[key] = val
            key = self.parse_str()
        
        return res

    def parse_header(self):
        major_version = self.take_i32()
        minor_version = self.take_i32()
        net_version = self.take_i32() if major_version > 865 and minor_version > 17 else None
        assert net_version != None

        game_type = self.parse_text()
        properties = self.parse_rdict()
        
        return {
            "major_version" : major_version,
            "minor_version" : minor_version,
            "net_version" : net_version,
            "game_type" : game_type,
            "properties" : properties
        }

    def parse(self):
        header_size = self.take_i32()
        header_crc = self.take_u32()
        header_data = self.view_data(header_size)
        header = self.parse_header()
        return json.dumps(header, indent=4)