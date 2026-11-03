"""Keep this process running for autonomous work while the UI is closed."""
import time
from hana_ai.agents import tick
from hana_ai.store import event

if __name__ == '__main__':
    print('Hana AI worker running. Ctrl+C to stop. Configure and enable agents in the app.')
    try:
        while True:
            try:
                tick()
            except Exception:
                event('Worker', 'error', 'Scheduler tick failed; will retry.')
            time.sleep(10)
    except KeyboardInterrupt:
        print('Worker stopped.')
