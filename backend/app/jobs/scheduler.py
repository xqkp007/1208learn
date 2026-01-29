from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..core.logging import get_logger
from ..core.settings import get_settings
from ..services.compare_kb_sync import CompareKbSyncService
from ..services.dialog_etl import DialogETLService
from ..services.faq_extraction import FAQExtractionService


logger = get_logger(__name__)
settings = get_settings()


class SchedulerManager:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone=settings.scheduler.timezone)
        self.etl_service = DialogETLService()
        self.faq_service = FAQExtractionService()
        self.compare_sync_service = CompareKbSyncService()
        self._configure_jobs()

    def _log_job_plan(self) -> None:
        jobs = self.scheduler.get_jobs()
        if not jobs:
            logger.warning("Scheduler has no jobs configured.")
            return
        for job in jobs:
            logger.info(
                "Scheduler job configured: id=%s next_run_time=%s trigger=%s",
                job.id,
                job.next_run_time,
                job.trigger,
            )

    def _configure_jobs(self) -> None:
        etl_trigger = CronTrigger.from_crontab(
            settings.scheduler.cron_expression,
            timezone=settings.scheduler.timezone,
        )
        self.scheduler.add_job(
            self._run_daily_etl,
            trigger=etl_trigger,
            id="daily_dialog_etl",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        faq_trigger = CronTrigger.from_crontab(
            settings.scheduler.faq_cron_expression,
            timezone=settings.scheduler.timezone,
        )
        self.scheduler.add_job(
            self._run_daily_faq_extraction,
            trigger=faq_trigger,
            id="daily_faq_extraction",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    def start(self) -> None:
        if not self.scheduler.running:
            logger.info(
                "Starting scheduler with ETL cron %s and FAQ cron %s (%s)",
                settings.scheduler.cron_expression,
                settings.scheduler.faq_cron_expression,
                settings.scheduler.timezone,
            )
            self.scheduler.start()
            self._log_job_plan()

    def shutdown(self) -> None:
        if self.scheduler.running:
            logger.info("Shutting down scheduler")
            self.scheduler.shutdown(wait=False)

    def _run_daily_etl(self) -> None:
        target_date = self.etl_service.default_target_date()
        logger.info("Scheduled ETL triggered for %s", target_date.isoformat())
        self.etl_service.run_for_date(target_date)

    def _run_daily_faq_extraction(self) -> None:
        logger.info("Scheduled FAQ extraction triggered.")
        self.faq_service.run()
        logger.info("Scheduled compare KB sync triggered.")
        self.compare_sync_service.run()
