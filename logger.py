import time

class Logger():
    def __init__(self, filename):
        self.logfile = open(filename, 'w')
        self.most_recent = ''

    def write(self, text):
        self.logfile.write(time.strftime('%d/%m/%Y %H:%M:%S - ') + text + '\n')
        self.most_recent = text

    def get_most_recent(self):
        return self.most_recent

    def close_file(self):
        self.logfile.close()