from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from core.config import get_settings
from core.batch import start_batch_job

scheduler = AsyncIOScheduler()

def job_wrapper():
    # Helper to wrap the blocking start_batch_job in an async-friendly way
    # Or just call it directly if AsyncIOScheduler can handle thread isolation (it usually runs in asyncio loop natively so blocking is bad)
    # Actually, start_batch_job is synchronous block, so we should run it in an executor
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, start_batch_job)

def get_scheduler():
    return scheduler

def configure_scheduler():
    settings = get_settings()
    cron_time = settings.get("cron_time", "02:00")
    
    # Remove existing jobs if any
    scheduler.remove_all_jobs()
    
    try:
        # Parse HH:MM
        hours, minutes = cron_time.split(":")
        trigger = CronTrigger(hour=int(hours), minute=int(minutes))
        scheduler.add_job(job_wrapper, trigger=trigger, id="batch_translation")
        print(f"Scheduler configured for everyday at: {cron_time}")
    except Exception as e:
        print(f"Error configuring scheduler (Invalid time format {cron_time}): {e}, falling back to default 2 AM")
        scheduler.add_job(job_wrapper, trigger=CronTrigger(hour=2, minute=0), id="batch_translation")
