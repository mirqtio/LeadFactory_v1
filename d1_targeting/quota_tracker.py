"""
Quota Tracker for D1 Targeting Domain

Manages daily quotas and fair allocation of targeting resources across campaigns.
Tracks usage, enforces limits, and provides analytics on quota utilization.
"""
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
import logging

from database.session import SessionLocal
from core.config import get_settings
from core.logging import get_logger
from .models import CampaignBatch, Campaign, CampaignTarget


class QuotaTracker:
    """
    Tracks and manages daily quotas for fair allocation across campaigns
    """
    
    def __init__(self, session: Optional[Session] = None):
        self.logger = get_logger("quota_tracker", domain="d1")
        self.session = session or SessionLocal()
        self.settings = get_settings()
        
        # Default quota settings (can be made configurable)
        self.default_daily_quota = 1000
        self.default_campaign_max_percentage = 0.4  # Max 40% of daily quota per campaign
        self.quota_reset_hour = 0  # Midnight UTC
    
    def get_daily_quota(self, target_date: Optional[date] = None) -> int:
        """
        Get the total daily quota for target processing
        
        Acceptance Criteria:
        - Quota allocation fair
        """
        if target_date is None:
            target_date = date.today()
        
        # For now, use default quota
        # In future, this could be configurable per day/period
        base_quota = self.default_daily_quota
        
        # Apply any adjustments based on historical performance
        utilization_factor = self._get_historical_utilization_factor(target_date)
        adjusted_quota = int(base_quota * utilization_factor)
        
        self.logger.debug(f"Daily quota for {target_date}: {adjusted_quota} (base: {base_quota}, factor: {utilization_factor})")
        
        return adjusted_quota
    
    def get_remaining_quota(self, target_date: Optional[date] = None) -> int:
        """Get remaining quota for the target date"""
        if target_date is None:
            target_date = date.today()
        
        total_quota = self.get_daily_quota(target_date)
        used_quota = self.get_used_quota(target_date)
        
        return max(0, total_quota - used_quota)
    
    def get_used_quota(self, target_date: Optional[date] = None) -> int:
        """Get quota already used for the target date"""
        if target_date is None:
            target_date = date.today()
        
        # Count all targets processed in batches for the target date
        used_quota = (
            self.session.query(func.sum(CampaignBatch.targets_processed))
            .filter(
                func.date(CampaignBatch.scheduled_at) == target_date,
                CampaignBatch.targets_processed.isnot(None)
            )
            .scalar() or 0
        )
        
        return used_quota
    
    def get_campaign_quota_allocation(self, campaign_id: str, target_date: Optional[date] = None) -> Dict[str, int]:
        """Get quota allocation details for a specific campaign"""
        if target_date is None:
            target_date = date.today()
        
        total_quota = self.get_daily_quota(target_date)
        campaign_used = self._get_campaign_used_quota(campaign_id, target_date)
        campaign_max = int(total_quota * self.default_campaign_max_percentage)
        campaign_remaining = max(0, campaign_max - campaign_used)
        
        return {
            'total_daily_quota': total_quota,
            'campaign_max_quota': campaign_max,
            'campaign_used_quota': campaign_used,
            'campaign_remaining_quota': campaign_remaining,
            'campaign_percentage_used': (campaign_used / campaign_max * 100) if campaign_max > 0 else 0
        }
    
    def _get_campaign_used_quota(self, campaign_id: str, target_date: date) -> int:
        """Get quota used by specific campaign on target date"""
        used = (
            self.session.query(func.sum(CampaignBatch.targets_processed))
            .filter(
                CampaignBatch.campaign_id == campaign_id,
                func.date(CampaignBatch.scheduled_at) == target_date,
                CampaignBatch.targets_processed.isnot(None)
            )
            .scalar() or 0
        )
        
        return used
    
    def is_quota_available(self, requested_quota: int, campaign_id: Optional[str] = None, target_date: Optional[date] = None) -> bool:
        """Check if requested quota is available"""
        if target_date is None:
            target_date = date.today()
        
        remaining_quota = self.get_remaining_quota(target_date)
        
        # Check global quota availability
        if requested_quota > remaining_quota:
            return False
        
        # Check campaign-specific quota limits if campaign specified
        if campaign_id:
            campaign_allocation = self.get_campaign_quota_allocation(campaign_id, target_date)
            if requested_quota > campaign_allocation['campaign_remaining_quota']:
                return False
        
        return True
    
    def reserve_quota(self, campaign_id: str, requested_quota: int, target_date: Optional[date] = None) -> bool:
        """
        Reserve quota for a campaign (used when creating batches)
        
        Returns True if reservation successful, False if quota not available
        """
        if target_date is None:
            target_date = date.today()
        
        if not self.is_quota_available(requested_quota, campaign_id, target_date):
            self.logger.warning(f"Quota reservation failed for campaign {campaign_id}: {requested_quota} requested")
            return False
        
        # Quota is available, reservation successful
        # Actual quota tracking happens when batches are processed
        self.logger.info(f"Reserved {requested_quota} quota for campaign {campaign_id} on {target_date}")
        return True
    
    def record_batch_completion(self, batch_id: str, targets_processed: int) -> None:
        """Record completion of a batch for quota tracking"""
        batch = self.session.query(CampaignBatch).filter_by(id=batch_id).first()
        if not batch:
            self.logger.error(f"Batch {batch_id} not found for quota recording")
            return
        
        # Quota is automatically tracked via CampaignBatch.targets_processed
        # which is already updated when mark_batch_completed is called
        
        self.logger.debug(f"Recorded {targets_processed} processed targets for batch {batch_id}")
    
    def get_quota_utilization_stats(self, days_back: int = 7) -> Dict[str, any]:
        """Get quota utilization statistics for analysis"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        # Get daily utilization
        daily_stats = []
        current_date = start_date
        
        while current_date <= end_date:
            daily_quota = self.get_daily_quota(current_date)
            daily_used = self.get_used_quota(current_date)
            utilization_rate = (daily_used / daily_quota * 100) if daily_quota > 0 else 0
            
            daily_stats.append({
                'date': current_date.isoformat(),
                'quota': daily_quota,
                'used': daily_used,
                'utilization_rate': round(utilization_rate, 2)
            })
            
            current_date += timedelta(days=1)
        
        # Calculate summary statistics
        total_quota = sum(stat['quota'] for stat in daily_stats)
        total_used = sum(stat['used'] for stat in daily_stats)
        avg_utilization = sum(stat['utilization_rate'] for stat in daily_stats) / len(daily_stats) if daily_stats else 0
        
        return {
            'period_days': days_back,
            'total_quota': total_quota,
            'total_used': total_used,
            'overall_utilization_rate': round((total_used / total_quota * 100) if total_quota > 0 else 0, 2),
            'average_daily_utilization': round(avg_utilization, 2),
            'daily_breakdown': daily_stats
        }
    
    def get_campaign_quota_usage(self, days_back: int = 7) -> List[Dict[str, any]]:
        """Get quota usage breakdown by campaign"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        # Get campaign usage summary
        results = (
            self.session.query(
                Campaign.id,
                Campaign.name,
                func.sum(CampaignBatch.targets_processed).label('total_processed'),
                func.count(CampaignBatch.id).label('total_batches'),
                func.avg(CampaignBatch.targets_processed).label('avg_batch_size')
            )
            .join(CampaignBatch, Campaign.id == CampaignBatch.campaign_id)
            .filter(
                func.date(CampaignBatch.scheduled_at) >= start_date,
                func.date(CampaignBatch.scheduled_at) <= end_date,
                CampaignBatch.targets_processed.isnot(None)
            )
            .group_by(Campaign.id, Campaign.name)
            .order_by(desc('total_processed'))
            .all()
        )
        
        campaign_usage = []
        total_quota_period = sum(self.get_daily_quota(start_date + timedelta(days=i)) for i in range(days_back + 1))
        
        for result in results:
            quota_percentage = (result.total_processed / total_quota_period * 100) if total_quota_period > 0 else 0
            
            campaign_usage.append({
                'campaign_id': result.id,
                'campaign_name': result.name,
                'total_processed': result.total_processed or 0,
                'total_batches': result.total_batches or 0,
                'avg_batch_size': round(float(result.avg_batch_size or 0), 1),
                'quota_percentage': round(quota_percentage, 2)
            })
        
        return campaign_usage
    
    def _get_historical_utilization_factor(self, target_date: date) -> float:
        """
        Calculate utilization factor based on historical performance
        Used to adjust daily quotas dynamically
        """
        # Look at last 7 days of utilization (excluding target_date)
        end_date = target_date - timedelta(days=1)
        start_date = end_date - timedelta(days=6)
        
        utilization_rates = []
        current_date = start_date
        
        while current_date <= end_date:
            daily_quota = self.default_daily_quota  # Use base quota for calculation
            daily_used = self.get_used_quota(current_date)
            
            if daily_quota > 0:
                utilization_rate = daily_used / daily_quota
                utilization_rates.append(utilization_rate)
            
            current_date += timedelta(days=1)
        
        if not utilization_rates:
            return 1.0  # Default factor
        
        avg_utilization = sum(utilization_rates) / len(utilization_rates)
        
        # Adjust factor based on utilization
        # If consistently under-utilized, reduce quota
        # If consistently over-utilized (somehow), increase quota
        if avg_utilization < 0.7:  # Under 70% utilization
            factor = 0.9  # Reduce by 10%
        elif avg_utilization > 0.95:  # Over 95% utilization
            factor = 1.1  # Increase by 10%
        else:
            factor = 1.0  # No adjustment
        
        return factor
    
    def get_quota_alerts(self) -> List[Dict[str, any]]:
        """Get quota-related alerts and warnings"""
        alerts = []
        today = date.today()
        
        # Check if approaching daily quota limit
        remaining_quota = self.get_remaining_quota(today)
        total_quota = self.get_daily_quota(today)
        utilization_rate = ((total_quota - remaining_quota) / total_quota * 100) if total_quota > 0 else 0
        
        if utilization_rate > 90:
            alerts.append({
                'type': 'high_utilization',
                'severity': 'warning',
                'message': f"Daily quota {utilization_rate:.1f}% utilized ({remaining_quota} remaining)",
                'date': today.isoformat()
            })
        
        # Check for campaigns approaching their limits
        active_campaigns = self.session.query(Campaign).filter(Campaign.status == 'running').all()
        
        for campaign in active_campaigns:
            campaign_allocation = self.get_campaign_quota_allocation(campaign.id, today)
            campaign_utilization = campaign_allocation['campaign_percentage_used']
            
            if campaign_utilization > 80:
                alerts.append({
                    'type': 'campaign_quota_limit',
                    'severity': 'warning',
                    'message': f"Campaign '{campaign.name}' at {campaign_utilization:.1f}% of daily quota limit",
                    'campaign_id': campaign.id,
                    'date': today.isoformat()
                })
        
        return alerts
    
    def optimize_quota_distribution(self, campaigns: List[str], total_quota: int) -> Dict[str, int]:
        """
        Optimize quota distribution across campaigns based on performance metrics
        
        Acceptance Criteria:
        - Quota allocation fair
        """
        if not campaigns:
            return {}
        
        optimization_data = {}
        
        # Gather performance data for each campaign
        for campaign_id in campaigns:
            campaign = self.session.query(Campaign).filter_by(id=campaign_id).first()
            if not campaign:
                continue
            
            # Calculate performance metrics
            performance_score = self._calculate_campaign_performance_score(campaign)
            remaining_targets = max(0, campaign.total_targets - campaign.contacted_targets)
            
            optimization_data[campaign_id] = {
                'performance_score': performance_score,
                'remaining_targets': remaining_targets,
                'current_utilization': self._get_campaign_used_quota(campaign_id, date.today())
            }
        
        # Distribute quota based on performance and remaining targets
        allocations = {}
        remaining_quota = total_quota
        
        # Sort campaigns by performance score
        sorted_campaigns = sorted(
            optimization_data.items(),
            key=lambda x: x[1]['performance_score'],
            reverse=True
        )
        
        for campaign_id, data in sorted_campaigns:
            if remaining_quota <= 0:
                allocations[campaign_id] = 0
                continue
            
            # Calculate fair allocation
            base_allocation = remaining_quota // len([c for c in sorted_campaigns if c[1]['remaining_targets'] > 0])
            performance_bonus = int(base_allocation * 0.2 * (data['performance_score'] / 100))
            
            allocated_quota = min(
                data['remaining_targets'],
                base_allocation + performance_bonus,
                remaining_quota,
                int(total_quota * self.default_campaign_max_percentage)  # Respect max percentage
            )
            
            allocations[campaign_id] = allocated_quota
            remaining_quota -= allocated_quota
        
        return allocations
    
    def _calculate_campaign_performance_score(self, campaign: Campaign) -> float:
        """Calculate performance score for campaign (0-100)"""
        if campaign.contacted_targets == 0:
            return 50.0  # Default score for new campaigns
        
        # Calculate rates
        response_rate = campaign.responded_targets / campaign.contacted_targets if campaign.contacted_targets > 0 else 0
        conversion_rate = campaign.converted_targets / campaign.contacted_targets if campaign.contacted_targets > 0 else 0
        
        # Calculate cost efficiency (lower cost per conversion is better)
        cost_efficiency = 1.0  # Default
        if campaign.converted_targets > 0 and campaign.cost_per_conversion:
            # Normalize cost efficiency (assuming $100 is average cost per conversion)
            cost_efficiency = max(0.1, min(2.0, 100 / float(campaign.cost_per_conversion)))
        
        # Weighted score
        score = (
            response_rate * 40 +      # 40% weight on response rate
            conversion_rate * 40 +    # 40% weight on conversion rate  
            (cost_efficiency - 1) * 10 + 50  # 20% weight on cost efficiency, baseline 50
        )
        
        return min(100.0, max(0.0, score * 100))  # Convert to 0-100 scale