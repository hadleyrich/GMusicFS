"""
'Efficient FIFO Buffer' from http://ben.timby.com/?p=139
Modified to be a blocking buffer, for use in gmusicfs
"""

import threading
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

MAX_BUFFER = 1024**2*4


class Buffer(object):
    """
    >>> b = Buffer()
    >>> b.write('one')
    >>> b.write('two')
    >>> b.read(3) == 'one'
    True
    >>> b.write('three')
    >>> b.read(3) == 'two'
    True
    >>> b.read(5) == 'three'
    True
    >>> b.write('four')
    >>> b.read() == 'four'
    True
    >>> b.read() == ''
    True
    """
    def __init__(self, max_size=MAX_BUFFER):
        self.buffers = []
        self.max_size = max_size
        self.lock = threading.Lock()
        self.eof = False
        self.read_pos = 0
        self.write_pos = 0
        self.done_first_write = False
        # Acquire the lock immediately, so that the first write occurs
        # before the first read:
        self.lock.acquire()

    def write(self, data):
        # Don't acquire the lock for the first write:
        if self.done_first_write:
            self.lock.acquire()
        try:
            if not self.buffers:
                self.buffers.append(StringIO())
                self.write_pos = 0
            buf = self.buffers[-1]
            buf.seek(self.write_pos)
            buf.write(data)
            if buf.tell() >= self.max_size:
                buf = StringIO()
                self.buffers.append(buf)
            self.write_pos = buf.tell()
        finally:
            self.lock.release()
        self.done_first_write = True

    def read(self, length=-1):
        read_buf = StringIO()
        remaining = length
        while True:
            self.lock.acquire()
            try:
                # Read will block forever until we close the file:
                if self.eof and len(self.buffers) == 0:
                    break
                elif len(self.buffers) == 0:
                    continue
                buf = self.buffers[0]
                buf.seek(self.read_pos)
                read_buf.write(buf.read(remaining))
                self.read_pos = buf.tell()
                if length == -1:
                    # we did not limit the read, we exhausted the buffer,
                    # so delete it, keep reading from remaining buffers.
                    del self.buffers[0]
                    self.read_pos = 0
                else:
                    # we limited the read so either we
                    # exhausted the buffer or not:
                    remaining = length - read_buf.tell()
                    if remaining > 0:
                        # exhausted, remove buffer, read more.
                        # keep reading from remaining buffers.
                        del self.buffers[0]
                        self.read_pos = 0
                    else:
                        break
            finally:
                self.lock.release()
        return read_buf.getvalue()

    def __len__(self):
        length = 0
        self.lock.acquire()
        try:
            for buf in self.buffers:
                buf.seek(0, 2)
                if buf == self.buffers[0]:
                    length += buf.tell() - self.read_pos
                else:
                    length += buf.tell()
            return length
        finally:
            self.lock.release()

    def close(self):
        self.eof = True
