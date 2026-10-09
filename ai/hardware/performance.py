"""Bounded timings: totals over the run, percentiles over the latest 2048 samples."""
from collections import deque
import math
import time


class Performance:
    def __init__(self):
        self.started = time.perf_counter()
        self.series = {}
        self.events = {}

    def event(self, name):
        self.events.setdefault(name, round((time.perf_counter()-self.started)*1000, 3))

    def add(self, name, milliseconds):
        item = self.series.setdefault(name, {'count': 0, 'sum': 0., 'max': 0., 'samples': deque(maxlen=2048)})
        value = max(0., milliseconds)
        item['count'] += 1
        item['sum'] += value
        item['max'] = max(item['max'], value)
        item['samples'].append(value)

    def snapshot(self):
        result = {}
        for name, item in self.series.items():
            values = sorted(item['samples'])
            result[name] = {'count': item['count'], 'mean_ms': round(item['sum']/item['count'], 3),
                            'max_ms': round(item['max'], 3),
                            'p50_ms': round(values[math.ceil(len(values)*.5)-1], 3),
                            'p95_ms': round(values[math.ceil(len(values)*.95)-1], 3),
                            'percentile_samples': len(values)}
        return {'schema': 'smartwear.performance/1', 'events_ms': dict(self.events),
                'elapsed_s': round(time.perf_counter()-self.started, 3),
                'percentile_scope': 'latest_2048_samples', 'stages': result}
