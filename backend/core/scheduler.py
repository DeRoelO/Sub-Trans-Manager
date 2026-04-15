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
    cron_expr = settings.get("cron_expression", "0 2 * * *") # e.g. "0 2 * * *" or "*/5 * * * *"
    
    # Remove existing jobs if any
    scheduler.remove_all_jobs()
    
    try:
        # Split simplified cron expression (minute hour day month day_of_week)
        parts = cron_expr.strip().split()
        if len(parts) == 5:
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4]
            )
            scheduler.add_job(job_wrapper, trigger=trigger, id="batch_translation")
            print(f"Scheduler configured with cron: {cron_expr}")
        else:
            print(f"Invalid cron expression: {cron_expr}, falling back to default 2 AM")
            scheduler.add_job(job_wrapper, trigger=CronTrigger(hour=2, minute=0), id="batch_translation")
    except Exception as e:
        print(f"Error configuring scheduler: {e}")
