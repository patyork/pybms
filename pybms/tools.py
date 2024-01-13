class IntBuffer:
    def __init__(self, data):
        self.data = data

    def __getitem__(self, s):
        if type(s) == int:
            return self.data[s]
        return IntBuffer(self.data[s.start:s.stop:s.step])
        
    def pop(self, n=1):
        temp = self.data[:n]
        self.data = self.data[n:]
        return int.from_bytes(temp, "big")

    def __len__(self):
        return len(self.data)

    def __str__(self):
        return self.data.decode("utf-8")
    def __repr__(self):
        return str(self.data)

def pickle_append(path, data):
    import pickle
    import os
    history = None
    if os.path.exists(path):
        with open(path, 'rb') as f:
            history = pickle.load(f)
    
    if history is not None:
        history.append(data)
    else:
        history = [data]
    
    with open(path, 'wb') as f:
        pickle.dump(history, f)