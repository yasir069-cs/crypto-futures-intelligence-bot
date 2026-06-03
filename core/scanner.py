"""Market Scanner - Main scanning logic"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from config import Config
from database import db
from utils.logger import get_logger
from core.okx_client import OKXClient
from core.analyzer import Analyzer

logger = get_logger(__name__)

class Scanner:
    """Market scanner for continuous monitoring"""
    
    def __init__(self, telegram_bot):
        self.telegram_bot = telegram_bot
        self.analyzer = Analyzer()
        self.is_running = False
        self.scan_interval = Config.SCAN_INTERVAL_HOURS * 3600
        self.last_scan = None
    
    async def start(self):
        """Start continuous scanning"""
        self.is_running = True
        logger.info(f"Scanner started. Scan interval: {Config.SCAN_INTERVAL_HOURS} hour(s)")
        
        try:
            while self.is_running:
                await self._run_scan()
                
                logger.info(f"Next scan in {Config.SCAN_INTERVAL_HOURS} hour(s)")
                await asyncio.sleep(self.scan_interval)
        except Exception as e:
            logger.error(f"Scanner error: {e}", exc_info=True)
            await self.telegram_bot.send_message(
                f"🚨 Bot Error\n\nScanner crashed: {str(e)}"
            )
    
    async def stop(self):
        """Stop scanning"""
        self.is_running = False
        logger.info("Scanner stopped")
    
    async def _run_scan(self):
        """Execute market scan"""
        logger.info("Starting market scan...")
        self.last_scan = datetime.utcnow()
        
        scan_results = {
            'pairs_scanned': 0,
            'signals_generated': 0,
            'errors': 0
        }
        
        async with OKXClient() as client:
            try:
                # Get all USDT perpetual pairs
                instruments = await client.get_instruments('SWAP')
                logger.info(f"Found {len(instruments)} USDT perpetual pairs")
                
                # Limit to max pairs to scan
                instruments = instruments[:Config.MAX_PAIRS_SCAN]
                
                # Scan each pair
                for inst in instruments:
                    try:
                        inst_id = inst.get('instId')
                        coin_name = inst_id.replace('-USDT-SWAP', '')
                        
                        signal = await self._analyze_pair(client, inst_id, coin_name)
                        
                        if signal:
                            # Check cooldown
                            if not db.check_cooldown(coin_name, signal['action']):
                                # Send alert
                                await self.telegram_bot.send_signal_alert(signal)
                                
                                # Store in database
                                db.insert_signal(signal)
                                
                                # Set cooldown
                                db.set_cooldown(coin_name, signal['action'], Config.ALERT_COOLDOWN_HOURS)
                                
                                scan_results['signals_generated'] += 1
                            else:
                                logger.debug(f"Cooldown active for {coin_name} {signal['action']}")
                        
                        scan_results['pairs_scanned'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error analyzing {inst_id}: {e}")
                        scan_results['errors'] += 1
                        continue
                
                # Log scan summary
                logger.info(
                    f"Scan completed: {scan_results['pairs_scanned']} pairs scanned, "
                    f"{scan_results['signals_generated']} signals generated, "
                    f"{scan_results['errors']} errors"
                )
                
            except Exception as e:
                logger.error(f"Scan failed: {e}", exc_info=True)
    
    async def _analyze_pair(self, client: OKXClient, inst_id: str, coin_name: str) -> Optional[Dict]:
        """Analyze single pair"""
        
        try:
            # Fetch data for all timeframes
            timeframe_data = {}
            for tf in ['15m', '1H', '4H', '1D']:
                candles = await client.get_candles(inst_id, tf, 100)
                if candles:
                    timeframe_data[tf] = candles
            
            if not timeframe_data:
                logger.debug(f"No candle data for {inst_id}")
                return None
            
            # Get current price
            ticker = await client.get_ticker(inst_id)
            if not ticker:
                return None
            
            current_price = float(ticker.get('last', 0))
            
            # Get OI data
            oi_data = await client.get_open_interest(inst_id)
            
            # Run analysis
            signal = await self.analyzer.analyze_pair(
                coin_name,
                timeframe_data,
                current_price,
                {},  # volume_data - can be enhanced
                oi_data or {}
            )
            if signal:
                # Add timeframe to signal for database insertion
                signal["timeframe"] = "1H" # Defaulting to 1H, can be made dynamic if needed
            
            return signal
            
        except Exception as e:
            logger.error(f"Error analyzing pair {inst_id}: {e}")
            return None
