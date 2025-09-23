import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import functools

class AsyncHelper:
    """Helper class to properly handle asyncio operations in Flask"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._loop = None
        self._thread = None
        self.start_event_loop()
    
    def start_event_loop(self):
        """Start a dedicated event loop in a separate thread"""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()
        
        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()
        
        # Wait for loop to be ready
        while self._loop is None:
            threading.Event().wait(0.01)
    
    def run_async(self, coro):
        """Run an async coroutine and return the result"""
        if self._loop is None:
            raise RuntimeError("Event loop not started")
        
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=30)  # 30 second timeout
    
    def run_async_safe(self, coro):
        """Run async coroutine with error handling"""
        try:
            return self.run_async(coro)
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def shutdown(self):
        """Shutdown the event loop"""
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread:
                self._thread.join(timeout=5)

# Global async helper instance
async_helper = AsyncHelper()
