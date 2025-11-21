"""HTTP Admin Server for managing accounts via API"""

import asyncio
import json
import logging
import re
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
from aiohttp import web
import aiohttp

from src.oauth2.manager import OAuth2Manager

logger = logging.getLogger('xoauth2_proxy')


class AdminServer:
    """HTTP server for administrative tasks like adding/removing accounts"""

    def __init__(
        self,
        accounts_path: Path,
        account_manager,
        oauth_manager: OAuth2Manager,
        host: str = '127.0.0.1',
        port: int = 9090,
        proxy_config = None
    ):
        # Ensure accounts_path is absolute (resolve relative paths)
        self.accounts_path = Path(accounts_path).resolve()
        self.account_manager = account_manager
        self.oauth_manager = oauth_manager
        self.host = host
        self.port = port
        self.proxy_config = proxy_config
        self.app = None
        self.runner = None
        self.site = None

        # Round-robin IP assignment state
        self.available_ips: List[str] = []
        self.ip_assignment_index: int = 0
        self.ip_assignment_lock = asyncio.Lock()  # Thread-safe IP assignment
        self._initialize_ip_pool()

    def _initialize_ip_pool(self):
        """
        Initialize available IP pool for round-robin assignment.
        Filters out all reserved/private IPs using comprehensive RFC filtering.
        """
        try:
            from src.utils.network import get_public_server_ips

            # Get IPv6 setting from config (default: False)
            use_ipv6 = False
            if self.proxy_config:
                try:
                    use_ipv6 = self.proxy_config.global_config.smtp.use_ipv6
                except AttributeError:
                    pass

            # Get public IPs (automatically filters out all reserved ranges)
            public_ips = get_public_server_ips(use_ipv6=use_ipv6)

            self.available_ips = public_ips

            if self.available_ips:
                logger.info(f"[AdminServer] Detected {len(self.available_ips)} public IP(s) for round-robin assignment: {', '.join(self.available_ips)}")
                logger.info(f"[AdminServer] IPv6 usage: {'enabled' if use_ipv6 else 'disabled'}")
            else:
                logger.warning("[AdminServer] No usable public IPs detected. Auto IP assignment disabled.")

        except Exception as e:
            logger.error(f"[AdminServer] Failed to detect server IPs: {e}")
            self.available_ips = []

    async def _get_next_ip(self) -> Optional[str]:
        """
        Get next IP in round-robin fashion (thread-safe)

        Returns:
            IP address or None if no IPs available
        """
        if not self.available_ips:
            return None

        # Thread-safe IP assignment
        async with self.ip_assignment_lock:
            # Get current IP
            ip = self.available_ips[self.ip_assignment_index]

            # Move to next IP (round-robin)
            self.ip_assignment_index = (self.ip_assignment_index + 1) % len(self.available_ips)

        return ip

    def _should_auto_assign_ip(self) -> bool:
        """Check if auto IP assignment should be enabled"""
        # Check if we have proxy_config and IP binding is enabled
        if not self.proxy_config:
            return False

        try:
            smtp_config = self.proxy_config.global_config.smtp
            return smtp_config.use_source_ip_binding and len(self.available_ips) > 0
        except AttributeError:
            return False

    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def _is_personal_microsoft_account(self, email: str) -> bool:
        """Check if email is a personal Microsoft account (not Azure AD/Office365)"""
        personal_domains = ['hotmail.com', 'outlook.com', 'live.com', 'msn.com']
        domain = email.split('@')[-1].lower()
        return domain in personal_domains

    def _get_oauth_endpoint(self, provider: str) -> str:
        """Get SMTP endpoint based on provider"""
        if provider == 'gmail':
            return 'smtp.gmail.com:587'
        elif provider == 'outlook':
            return 'smtp.office365.com:587'
        else:
            return ''

    def _get_token_url(self, provider: str, email: str = '') -> str:
        """Get OAuth2 token URL based on provider and account type"""
        if provider == 'gmail':
            return 'https://oauth2.googleapis.com/token'
        elif provider == 'outlook':
            # Personal Microsoft accounts use different endpoint
            if email and self._is_personal_microsoft_account(email):
                return 'https://login.live.com/oauth20_token.srf'
            else:
                # Azure AD / Office365 organizational accounts
                return 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
        else:
            return ''

    async def _verify_oauth_credentials(self, account_data: Dict[str, Any]) -> tuple[bool, str, Optional[dict]]:
        """
        Verify OAuth2 credentials by attempting token refresh

        Returns:
            Tuple of (success: bool, message: str, token_data: Optional[dict])
        """
        provider = account_data['provider']
        email = account_data['email']

        # Get correct token URL based on provider and account type
        token_url = self._get_token_url(provider, email)

        if not token_url:
            return False, f"Unknown provider: {provider}", None

        try:
            if provider == 'gmail':
                post_data = {
                    'client_id': account_data['client_id'],
                    'client_secret': account_data['client_secret'],
                    'refresh_token': account_data['refresh_token'],
                    'grant_type': 'refresh_token'
                }
            elif provider == 'outlook':
                # Outlook/Microsoft accounts (both personal and organizational)
                # IMPORTANT: Do NOT include scope parameter during token refresh
                # The refresh token already has scopes embedded from initial authorization
                # Requesting different scopes will cause "unauthorized or expired" error
                post_data = {
                    'client_id': account_data['client_id'],
                    'refresh_token': account_data['refresh_token'],
                    'grant_type': 'refresh_token',
                    # NO SCOPE - matches OAuth2Manager behavior
                }

                # Add client_secret only if provided
                if account_data.get('client_secret'):
                    post_data['client_secret'] = account_data['client_secret']

            # Use aiohttp for async request (3s timeout - OAuth2 APIs respond in 1-2s typically)
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=post_data, timeout=aiohttp.ClientTimeout(total=3)) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        access_token = token_data.get('access_token')
                        if access_token:
                            return True, "Credentials verified", token_data
                        else:
                            return False, "No access token in response", None
                    else:
                        error_text = await response.text()
                        try:
                            error_json = json.loads(error_text)
                            error_msg = error_json.get('error_description', error_text)
                        except:
                            error_msg = error_text
                        return False, f"Token refresh failed: {error_msg}", None

        except asyncio.TimeoutError:
            return False, "Request timeout", None
        except Exception as e:
            return False, f"Verification error: {str(e)}", None

    def _load_accounts(self) -> list:
        """Load existing accounts from JSON file"""
        if not self.accounts_path.exists():
            return []

        try:
            with open(self.accounts_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Handle both formats: array at root or {"accounts": [...]}
                # This matches the ConfigLoader logic for consistency
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    # Check if it's {"accounts": [...]} format
                    return data.get('accounts', [])
                else:
                    return []
        except json.JSONDecodeError:
            logger.error(f"[AdminServer] Invalid JSON in {self.accounts_path}")
            return []
        except Exception as e:
            logger.error(f"[AdminServer] Error loading {self.accounts_path}: {e}")
            return []

    def _save_accounts(self, accounts: list) -> bool:
        """Save accounts to JSON file"""
        try:
            # Ensure parent directory exists (handles both relative and absolute paths)
            parent_dir = self.accounts_path.parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"[AdminServer] Created directory: {parent_dir}")

            # Save with pretty formatting
            with open(self.accounts_path, 'w', encoding='utf-8') as f:
                json.dump(accounts, f, indent=2, ensure_ascii=False)

            logger.debug(f"[AdminServer] Saved {len(accounts)} accounts to {self.accounts_path}")
            return True
        except Exception as e:
            logger.error(
                f"[AdminServer] Error saving {self.accounts_path}: {e}\n"
                f"  Absolute path: {self.accounts_path.absolute()}\n"
                f"  Parent dir: {self.accounts_path.parent} (exists: {self.accounts_path.parent.exists()})"
            )
            return False

    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint"""
        return web.json_response({'status': 'healthy', 'service': 'xoauth2-proxy-admin'})

    async def handle_add_account(self, request: web.Request) -> web.Response:
        """Handle POST /admin/accounts - Add a new account"""
        try:
            # Parse JSON body
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response(
                    {'success': False, 'error': 'Invalid JSON'},
                    status=400
                )

            # Validate required fields
            required_fields = ['email', 'provider', 'client_id', 'refresh_token']
            missing_fields = [f for f in required_fields if f not in data or not data[f]]

            if missing_fields:
                return web.json_response(
                    {'success': False, 'error': f'Missing required fields: {", ".join(missing_fields)}'},
                    status=400
                )

            # Validate email format
            email = data['email'].strip()
            if not self._validate_email(email):
                return web.json_response(
                    {'success': False, 'error': 'Invalid email format'},
                    status=400
                )

            # Validate provider
            provider = data['provider'].strip().lower()
            if provider not in ['gmail', 'outlook']:
                return web.json_response(
                    {'success': False, 'error': 'Provider must be "gmail" or "outlook"'},
                    status=400
                )

            # For Gmail, client_secret is required
            if provider == 'gmail' and not data.get('client_secret'):
                return web.json_response(
                    {'success': False, 'error': 'client_secret is required for Gmail'},
                    status=400
                )

            # Auto-detect oauth_endpoint (SMTP endpoint)
            oauth_endpoint = self._get_oauth_endpoint(provider)

            # Auto-detect oauth_token_url (OAuth2 token endpoint) based on account type
            oauth_token_url = data.get('oauth_token_url') or self._get_token_url(provider, email)

            # Generate account_id and vmta_name if not provided
            account_id = data.get('account_id', f"{provider}_{email.replace('@', '_').replace('.', '_')}")
            vmta_name = data.get('vmta_name', f"vmta-{provider}-{email.split('@')[0]}")

            # Get IP address (optional, with auto-assignment)
            ip_address = data.get('ip_address', '').strip()

            # Auto-assign IP if not provided and IP binding is enabled
            if not ip_address and self._should_auto_assign_ip():
                auto_ip = await self._get_next_ip()
                if auto_ip:
                    ip_address = auto_ip
                    logger.info(f"[AdminServer] Auto-assigned IP {ip_address} to {email} (round-robin)")

            # Build account object
            account = {
                'account_id': account_id,
                'email': email,
                'ip_address': ip_address,
                'vmta_name': vmta_name,
                'provider': provider,
                'oauth_endpoint': oauth_endpoint,
                'oauth_token_url': oauth_token_url,
                'client_id': data['client_id'].strip(),
                'refresh_token': data['refresh_token'].strip()
            }

            # Only add client_secret if provided
            if data.get('client_secret'):
                account['client_secret'] = data['client_secret'].strip()

            # Verify credentials if requested
            verify = data.get('verify', True)  # Default to True
            if verify:
                logger.info(f"[AdminServer] Verifying credentials for {email}...")
                success, message, token_data = await self._verify_oauth_credentials(account)
                if not success:
                    return web.json_response(
                        {'success': False, 'error': f'OAuth2 verification failed: {message}'},
                        status=400
                    )

                # Cache the verification token for immediate reuse
                if token_data:
                    await self.oauth_manager.cache_verification_token(email, token_data)

            # Load existing accounts
            accounts = self._load_accounts()

            # Check for duplicate
            existing_emails = [acc.get('email') for acc in accounts]
            overwrite = data.get('overwrite', False)

            if email in existing_emails:
                if not overwrite:
                    return web.json_response(
                        {
                            'success': False,
                            'error': f'Account {email} already exists. Use "overwrite": true to replace it.'
                        },
                        status=409  # Conflict
                    )
                # Remove old account
                accounts = [acc for acc in accounts if acc.get('email') != email]
                logger.info(f"[AdminServer] Overwriting existing account: {email}")

            # Add new account
            accounts.append(account)

            # Save to file
            if not self._save_accounts(accounts):
                return web.json_response(
                    {'success': False, 'error': 'Failed to save accounts to file'},
                    status=500
                )

            logger.info(f"[AdminServer] Account {email} added successfully ({len(accounts)} total)")

            # Trigger hot-reload of accounts
            try:
                num_accounts = await self.account_manager.reload()
                logger.info(f"[AdminServer] Accounts reloaded: {num_accounts} accounts active")
            except Exception as e:
                logger.error(f"[AdminServer] Error reloading accounts: {e}")
                # Continue anyway - account was saved to file

            return web.json_response({
                'success': True,
                'message': f'Account {email} added successfully',
                'total_accounts': len(accounts),
                'account': {
                    'account_id': account['account_id'],
                    'email': account['email'],
                    'ip_address': account['ip_address'],
                    'vmta_name': account['vmta_name'],
                    'provider': account['provider'],
                    'oauth_endpoint': account['oauth_endpoint'],
                    'oauth_token_url': account['oauth_token_url']
                }
            })

        except Exception as e:
            logger.error(f"[AdminServer] Error adding account: {e}", exc_info=True)
            return web.json_response(
                {'success': False, 'error': f'Internal server error: {str(e)}'},
                status=500
            )

    async def handle_list_accounts(self, request: web.Request) -> web.Response:
        """Handle GET /admin/accounts - List all accounts (without sensitive data)"""
        try:
            accounts = self._load_accounts()

            # Return without sensitive fields
            safe_accounts = [
                {
                    'account_id': acc.get('account_id'),
                    'email': acc.get('email'),
                    'ip_address': acc.get('ip_address', ''),
                    'vmta_name': acc.get('vmta_name'),
                    'provider': acc.get('provider'),
                    'oauth_endpoint': acc.get('oauth_endpoint'),
                    'oauth_token_url': acc.get('oauth_token_url')
                }
                for acc in accounts
            ]

            return web.json_response({
                'success': True,
                'total_accounts': len(safe_accounts),
                'accounts': safe_accounts
            })

        except Exception as e:
            logger.error(f"[AdminServer] Error listing accounts: {e}", exc_info=True)
            return web.json_response(
                {'success': False, 'error': f'Internal server error: {str(e)}'},
                status=500
            )

    async def handle_delete_account(self, request: web.Request) -> web.Response:
        """Handle DELETE /admin/accounts/{email} - Delete a specific account"""
        try:
            email = request.match_info.get('email', '').strip()

            if not email:
                return web.json_response(
                    {'success': False, 'error': 'Email parameter is required'},
                    status=400
                )

            # Validate email format
            if not self._validate_email(email):
                return web.json_response(
                    {'success': False, 'error': 'Invalid email format'},
                    status=400
                )

            # Load accounts
            accounts = self._load_accounts()

            # Find and remove account
            original_count = len(accounts)
            accounts = [acc for acc in accounts if acc.get('email') != email]

            if len(accounts) == original_count:
                return web.json_response(
                    {'success': False, 'error': f'Account {email} not found'},
                    status=404
                )

            # Save updated accounts
            if not self._save_accounts(accounts):
                return web.json_response(
                    {'success': False, 'error': 'Failed to save accounts to file'},
                    status=500
                )

            logger.info(f"[AdminServer] Account {email} deleted successfully ({len(accounts)} remaining)")

            # Trigger hot-reload
            try:
                num_accounts = await self.account_manager.reload()
                logger.info(f"[AdminServer] Accounts reloaded: {num_accounts} accounts active")
            except Exception as e:
                logger.error(f"[AdminServer] Error reloading accounts: {e}")

            return web.json_response({
                'success': True,
                'message': f'Account {email} deleted successfully',
                'total_accounts': len(accounts)
            })

        except Exception as e:
            logger.error(f"[AdminServer] Error deleting account: {e}", exc_info=True)
            return web.json_response(
                {'success': False, 'error': f'Internal server error: {str(e)}'},
                status=500
            )

    async def handle_delete_all_accounts(self, request: web.Request) -> web.Response:
        """Handle DELETE /admin/accounts - Delete all accounts (requires confirmation)"""
        try:
            # Require explicit confirmation to prevent accidental deletion
            confirm = request.rel_url.query.get('confirm', '').lower()

            if confirm != 'true':
                return web.json_response(
                    {
                        'success': False,
                        'error': 'Confirmation required. Use ?confirm=true to delete all accounts'
                    },
                    status=400
                )

            # Load accounts
            accounts = self._load_accounts()
            original_count = len(accounts)

            if original_count == 0:
                return web.json_response(
                    {'success': False, 'error': 'No accounts to delete'},
                    status=404
                )

            # Delete all accounts
            if not self._save_accounts([]):
                return web.json_response(
                    {'success': False, 'error': 'Failed to save accounts to file'},
                    status=500
                )

            logger.warning(f"[AdminServer] All accounts deleted ({original_count} accounts removed)")

            # Trigger hot-reload
            try:
                num_accounts = await self.account_manager.reload()
                logger.info(f"[AdminServer] Accounts reloaded: {num_accounts} accounts active")
            except Exception as e:
                logger.error(f"[AdminServer] Error reloading accounts: {e}")

            return web.json_response({
                'success': True,
                'message': f'All accounts deleted ({original_count} accounts removed)',
                'total_accounts': 0
            })

        except Exception as e:
            logger.error(f"[AdminServer] Error deleting all accounts: {e}", exc_info=True)
            return web.json_response(
                {'success': False, 'error': f'Internal server error: {str(e)}'},
                status=500
            )

    async def handle_delete_invalid_accounts(self, request: web.Request) -> web.Response:
        """Handle DELETE /admin/accounts/invalid - Delete accounts with bad OAuth2 credentials"""
        try:
            # Load accounts
            accounts = self._load_accounts()
            original_count = len(accounts)

            if original_count == 0:
                return web.json_response(
                    {'success': False, 'error': 'No accounts to check'},
                    status=404
                )

            # Test each account's OAuth2 credentials
            logger.info(f"[AdminServer] Testing {original_count} accounts for validity...")

            valid_accounts = []
            invalid_accounts = []

            for account in accounts:
                success, message, token_data = await self._verify_oauth_credentials(account)

                if success:
                    valid_accounts.append(account)
                    logger.info(f"[AdminServer] ✓ {account['email']} - Valid")

                    # Cache the token for immediate reuse
                    if token_data:
                        await self.oauth_manager.cache_verification_token(account['email'], token_data)
                else:
                    invalid_accounts.append(account['email'])
                    logger.warning(f"[AdminServer] ✗ {account['email']} - Invalid: {message}")

            # If no invalid accounts found
            if len(invalid_accounts) == 0:
                return web.json_response({
                    'success': True,
                    'message': 'No invalid accounts found',
                    'total_accounts': len(valid_accounts),
                    'deleted_count': 0,
                    'deleted_accounts': []
                })

            # Save only valid accounts
            if not self._save_accounts(valid_accounts):
                return web.json_response(
                    {'success': False, 'error': 'Failed to save accounts to file'},
                    status=500
                )

            logger.warning(
                f"[AdminServer] Deleted {len(invalid_accounts)} invalid accounts: {', '.join(invalid_accounts)}"
            )

            # Trigger hot-reload
            try:
                num_accounts = await self.account_manager.reload()
                logger.info(f"[AdminServer] Accounts reloaded: {num_accounts} accounts active")
            except Exception as e:
                logger.error(f"[AdminServer] Error reloading accounts: {e}")

            return web.json_response({
                'success': True,
                'message': f'Deleted {len(invalid_accounts)} invalid accounts',
                'total_accounts': len(valid_accounts),
                'deleted_count': len(invalid_accounts),
                'deleted_accounts': invalid_accounts
            })

        except Exception as e:
            logger.error(f"[AdminServer] Error deleting invalid accounts: {e}", exc_info=True)
            return web.json_response(
                {'success': False, 'error': f'Internal server error: {str(e)}'},
                status=500
            )

    async def handle_add_accounts_batch(self, request: web.Request) -> web.Response:
        """Handle POST /admin/accounts/batch - Add multiple accounts with parallel verification"""
        try:
            # Parse JSON body
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response(
                    {'success': False, 'error': 'Invalid JSON'},
                    status=400
                )

            # Validate it's a list
            if not isinstance(data, list):
                return web.json_response(
                    {'success': False, 'error': 'Body must be an array of account objects'},
                    status=400
                )

            if len(data) == 0:
                return web.json_response(
                    {'success': False, 'error': 'Empty array provided'},
                    status=400
                )

            if len(data) > 100:
                return web.json_response(
                    {'success': False, 'error': 'Maximum 100 accounts per batch'},
                    status=400
                )

            logger.info(f"[AdminServer] Batch adding {len(data)} accounts...")

            # Verify all accounts in parallel
            verification_tasks = []
            accounts_to_add = []

            for idx, account_data in enumerate(data):
                # Validate required fields
                required_fields = ['email', 'provider', 'client_id', 'refresh_token']
                missing_fields = [f for f in required_fields if f not in account_data or not account_data[f]]

                if missing_fields:
                    return web.json_response(
                        {
                            'success': False,
                            'error': f'Account {idx}: Missing required fields: {", ".join(missing_fields)}'
                        },
                        status=400
                    )

                email = account_data['email'].strip()
                provider = account_data['provider'].strip().lower()

                # Validate
                if not self._validate_email(email):
                    return web.json_response(
                        {'success': False, 'error': f'Account {idx}: Invalid email format: {email}'},
                        status=400
                    )

                if provider not in ['gmail', 'outlook']:
                    return web.json_response(
                        {'success': False, 'error': f'Account {idx}: Provider must be "gmail" or "outlook"'},
                        status=400
                    )

                if provider == 'gmail' and not account_data.get('client_secret'):
                    return web.json_response(
                        {'success': False, 'error': f'Account {idx}: client_secret required for Gmail'},
                        status=400
                    )

                # Build account object
                oauth_endpoint = self._get_oauth_endpoint(provider)
                oauth_token_url = account_data.get('oauth_token_url') or self._get_token_url(provider, email)
                account_id = account_data.get('account_id', f"{provider}_{email.replace('@', '_').replace('.', '_')}")
                vmta_name = account_data.get('vmta_name', f"vmta-{provider}-{email.split('@')[0]}")

                # Get or auto-assign IP
                ip_address = account_data.get('ip_address', '').strip()
                if not ip_address and self._should_auto_assign_ip():
                    auto_ip = await self._get_next_ip()
                    if auto_ip:
                        ip_address = auto_ip

                account = {
                    'account_id': account_id,
                    'email': email,
                    'ip_address': ip_address,
                    'vmta_name': vmta_name,
                    'provider': provider,
                    'oauth_endpoint': oauth_endpoint,
                    'oauth_token_url': oauth_token_url,
                    'client_id': account_data['client_id'].strip(),
                    'refresh_token': account_data['refresh_token'].strip()
                }

                if account_data.get('client_secret'):
                    account['client_secret'] = account_data['client_secret'].strip()

                accounts_to_add.append(account)

                # Add verification task if requested
                verify = account_data.get('verify', True)
                if verify:
                    verification_tasks.append(self._verify_oauth_credentials(account))

            # Verify all accounts in parallel (MUCH faster!)
            if verification_tasks:
                start_time = time.time()
                results = await asyncio.gather(*verification_tasks, return_exceptions=True)
                duration = time.time() - start_time
                logger.debug(f"[AdminServer] Verified {len(verification_tasks)} accounts in parallel ({duration:.2f}s)")

                # Check results
                failed_accounts = []
                for idx, result in enumerate(results):
                    if isinstance(result, Exception):
                        failed_accounts.append({
                            'email': accounts_to_add[idx]['email'],
                            'error': str(result)
                        })
                    elif not result[0]:  # (success, message, token_data)
                        failed_accounts.append({
                            'email': accounts_to_add[idx]['email'],
                            'error': result[1]
                        })
                    else:
                        # Cache verification token
                        if result[2]:
                            await self.oauth_manager.cache_verification_token(accounts_to_add[idx]['email'], result[2])

                if failed_accounts:
                    return web.json_response(
                        {
                            'success': False,
                            'error': f'{len(failed_accounts)} accounts failed verification',
                            'failed_accounts': failed_accounts
                        },
                        status=400
                    )

            # Load existing accounts
            existing_accounts = self._load_accounts()
            existing_emails = {acc.get('email') for acc in existing_accounts}

            # Check for duplicates and handle overwrite
            duplicates = [acc['email'] for acc in accounts_to_add if acc['email'] in existing_emails]

            if duplicates:
                # Check if any account in batch has overwrite=true
                has_overwrite = any(account_data.get('overwrite', False) for account_data in data)

                if not has_overwrite:
                    return web.json_response(
                        {
                            'success': False,
                            'error': f'{len(duplicates)} accounts already exist. Use "overwrite": true to replace them.',
                            'duplicates': duplicates
                        },
                        status=409
                    )

                # Remove duplicates if any account has overwrite
                emails_to_add = {acc['email'] for acc in accounts_to_add}
                existing_accounts = [acc for acc in existing_accounts if acc.get('email') not in emails_to_add]

            # Add new accounts
            all_accounts = existing_accounts + accounts_to_add

            # Save to file
            if not self._save_accounts(all_accounts):
                return web.json_response(
                    {'success': False, 'error': 'Failed to save accounts to file'},
                    status=500
                )

            logger.info(f"[AdminServer] Batch added {len(accounts_to_add)} accounts ({len(all_accounts)} total)")

            # Trigger hot-reload
            try:
                num_accounts = await self.account_manager.reload()
                logger.info(f"[AdminServer] Accounts reloaded: {num_accounts} accounts active")
            except Exception as e:
                logger.error(f"[AdminServer] Error reloading accounts: {e}")

            return web.json_response({
                'success': True,
                'message': f'Added {len(accounts_to_add)} accounts successfully',
                'total_accounts': len(all_accounts),
                'added_count': len(accounts_to_add)
            })

        except Exception as e:
            logger.error(f"[AdminServer] Error in batch add: {e}", exc_info=True)
            return web.json_response(
                {'success': False, 'error': f'Internal server error: {str(e)}'},
                status=500
            )

    async def start(self):
        """Start the admin HTTP server"""
        try:
            self.app = web.Application()

            # Add routes
            self.app.router.add_get('/health', self.handle_health)
            self.app.router.add_get('/admin/accounts', self.handle_list_accounts)
            self.app.router.add_post('/admin/accounts', self.handle_add_account)
            self.app.router.add_post('/admin/accounts/batch', self.handle_add_accounts_batch)  # ✅ NEW: Batch endpoint
            self.app.router.add_delete('/admin/accounts/{email}', self.handle_delete_account)
            self.app.router.add_delete('/admin/accounts/invalid', self.handle_delete_invalid_accounts)
            self.app.router.add_delete('/admin/accounts', self.handle_delete_all_accounts)

            # Setup runner
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            # Create site
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()

            logger.info(f"[AdminServer] Admin HTTP server started on http://{self.host}:{self.port}")
            logger.info(f"[AdminServer] Health check: GET http://{self.host}:{self.port}/health")
            logger.info(f"[AdminServer] List accounts: GET http://{self.host}:{self.port}/admin/accounts")
            logger.info(f"[AdminServer] Add account: POST http://{self.host}:{self.port}/admin/accounts")
            logger.info(f"[AdminServer] Add accounts (batch, parallel): POST http://{self.host}:{self.port}/admin/accounts/batch")
            logger.info(f"[AdminServer] Delete account: DELETE http://{self.host}:{self.port}/admin/accounts/{{email}}")
            logger.info(f"[AdminServer] Delete invalid: DELETE http://{self.host}:{self.port}/admin/accounts/invalid")
            logger.info(f"[AdminServer] Delete all: DELETE http://{self.host}:{self.port}/admin/accounts?confirm=true")

        except Exception as e:
            logger.error(f"[AdminServer] Failed to start admin server: {e}")
            raise

    async def shutdown(self):
        """Shutdown the admin server"""
        logger.info("[AdminServer] Shutting down admin server...")

        try:
            # Clean up the runner (this handles stopping the site AND cleaning up)
            # Do NOT manually stop the site first - runner.cleanup() handles it
            # Check that runner is not None AND has a valid app reference
            if self.runner and hasattr(self.runner, '_app') and self.runner._app is not None:
                await self.runner.cleanup()
                logger.debug("[AdminServer] Runner and site cleaned up")
            elif self.runner:
                logger.debug("[AdminServer] Runner exists but not properly initialized, skipping cleanup")
        except Exception as e:
            logger.warning(f"[AdminServer] Error cleaning up runner: {e}")

        # Reset references
        self.runner = None
        self.site = None
        self.app = None

        logger.info("[AdminServer] Admin server stopped")
