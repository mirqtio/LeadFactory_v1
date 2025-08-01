"""
D0 Gateway facade - unified interface for all external APIs
"""

from decimal import Decimal
from typing import Any

from core.logging import get_logger

from .factory import GatewayClientFactory, get_gateway_factory
from .metrics import GatewayMetrics


class GatewayFacade:
    """
    Unified facade for all external API operations.
    Provides a single entry point for PageSpeed, OpenAI, SendGrid, and Stripe APIs.
    """

    def __init__(self, factory: GatewayClientFactory | None = None):
        """
        Initialize the gateway facade

        Args:
            factory: Optional factory instance (uses global if None)
        """
        self.logger = get_logger("gateway.facade", domain="d0")
        self.factory = factory or get_gateway_factory()
        self.metrics = GatewayMetrics()

        self.logger.info("Gateway facade initialized")

    # PageSpeed API Methods
    async def analyze_website(
        self, url: str, strategy: str = "mobile", categories: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Analyze website performance using PageSpeed Insights

        Args:
            url: Website URL to analyze
            strategy: Analysis strategy ('mobile' or 'desktop')
            categories: Categories to analyze (performance, accessibility, etc.)

        Returns:
            PageSpeed analysis results
        """
        try:
            client = self.factory.create_client("pagespeed")
            result = await client.analyze_url(url=url, strategy=strategy, categories=categories)

            self.logger.info(f"PageSpeed analysis completed: {url} ({strategy})")
            return result

        except Exception as e:
            self.logger.error(f"PageSpeed analysis failed: {e}")
            raise

    async def get_core_web_vitals(self, url: str, strategy: str = "mobile") -> dict[str, Any]:
        """
        Get Core Web Vitals for a website

        Args:
            url: Website URL to analyze
            strategy: Analysis strategy ('mobile' or 'desktop')

        Returns:
            Core Web Vitals data
        """
        try:
            client = self.factory.create_client("pagespeed")
            result = await client.get_core_web_vitals(url, strategy)

            self.logger.info(f"Core Web Vitals retrieved: {url}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get Core Web Vitals: {e}")
            raise

    async def analyze_multiple_websites(self, urls: list[str], strategy: str = "mobile") -> dict[str, Any]:
        """
        Analyze multiple websites in parallel

        Args:
            urls: List of URLs to analyze
            strategy: Analysis strategy

        Returns:
            Results for all URLs
        """
        try:
            client = self.factory.create_client("pagespeed")
            result = await client.batch_analyze_urls(urls, strategy)

            self.logger.info(f"Batch analysis completed: {len(urls)} URLs")
            return result

        except Exception as e:
            self.logger.error(f"Batch analysis failed: {e}")
            raise

    # OpenAI API Methods
    async def generate_website_insights(
        self,
        pagespeed_data: dict[str, Any],
        business_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate AI-powered website insights from PageSpeed data

        Args:
            pagespeed_data: PageSpeed Insights results
            business_context: Additional business context

        Returns:
            AI-generated insights and recommendations
        """
        try:
            client = self.factory.create_client("openai")
            result = await client.analyze_website_performance(
                pagespeed_data=pagespeed_data, business_context=business_context
            )

            self.logger.info("Website insights generated")
            return result

        except Exception as e:
            self.logger.error(f"Failed to generate website insights: {e}")
            raise

    async def generate_personalized_email(
        self,
        business_name: str,
        website_issues: list[dict[str, Any]],
        recipient_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate personalized email content for outreach

        Args:
            business_name: Name of the business
            website_issues: List of identified website issues
            recipient_name: Name of the recipient (if known)

        Returns:
            Generated email content
        """
        try:
            client = self.factory.create_client("openai")
            result = await client.generate_email_content(
                business_name=business_name,
                website_issues=website_issues,
                recipient_name=recipient_name,
            )

            self.logger.info(f"Email content generated for {business_name}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to generate email content: {e}")
            raise

    # SendGrid API Methods
    async def send_email(
        self,
        to_email: str,
        from_email: str,
        from_name: str,
        subject: str,
        html_content: str,
        text_content: str | None = None,
        reply_to: str | None = None,
        template_id: str | None = None,
        dynamic_template_data: dict[str, Any] | None = None,
        custom_args: dict[str, str] | None = None,
        tracking_settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send email via SendGrid

        Args:
            to_email: Recipient email address
            from_email: Sender email address
            from_name: Sender name
            subject: Email subject
            html_content: HTML content of the email
            text_content: Plain text content (optional)
            reply_to: Reply-to email address
            template_id: Dynamic template ID
            dynamic_template_data: Data for dynamic templates
            custom_args: Custom arguments for webhook tracking
            tracking_settings: Email tracking settings

        Returns:
            SendGrid response with message ID and status
        """
        try:
            client = self.factory.create_client("sendgrid")

            result = await client.send_email(
                to_email=to_email,
                from_email=from_email,
                from_name=from_name,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                reply_to=reply_to,
                template_id=template_id,
                dynamic_template_data=dynamic_template_data,
                custom_args=custom_args,
                tracking_settings=tracking_settings,
            )

            self.logger.info(f"Email sent to {to_email}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            raise

    async def send_bulk_emails(
        self,
        emails: list[dict[str, Any]],
        from_email: str,
        from_name: str | None = None,
        template_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Send multiple emails efficiently

        Args:
            emails: List of email dictionaries with to_email, subject, content
            from_email: Sender email address
            from_name: Sender name
            template_id: Dynamic template ID

        Returns:
            Bulk send results
        """
        try:
            client = self.factory.create_client("sendgrid")

            result = await client.send_bulk_emails(
                emails=emails,
                from_email=from_email,
                from_name=from_name,
                template_id=template_id,
            )

            self.logger.info(f"Bulk email sent: {result['sent']} sent, {result['failed']} failed")
            return result

        except Exception as e:
            self.logger.error(f"Failed to send bulk emails: {e}")
            raise

    async def get_email_stats(
        self,
        start_date: str,
        end_date: str | None = None,
        aggregated_by: str = "day",
    ) -> dict[str, Any]:
        """
        Get SendGrid email statistics

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            aggregated_by: Aggregation period (day, week, month)

        Returns:
            Email statistics
        """
        try:
            client = self.factory.create_client("sendgrid")
            result = await client.get_email_stats(start_date=start_date, end_date=end_date, aggregated_by=aggregated_by)

            self.logger.info(f"SendGrid statistics retrieved: {start_date} to {end_date}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get SendGrid statistics: {e}")
            raise

    async def get_bounces(
        self,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Get bounce information from SendGrid

        Args:
            start_time: Start timestamp
            end_time: End timestamp
            limit: Number of results to return
            offset: Offset for pagination

        Returns:
            Bounce information
        """
        try:
            client = self.factory.create_client("sendgrid")
            result = await client.get_bounces(start_time=start_time, end_time=end_time, limit=limit, offset=offset)

            self.logger.info("Retrieved bounce information")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get bounces: {e}")
            raise

    async def delete_bounce(self, email: str) -> dict[str, Any]:
        """
        Remove an email from the bounce list

        Args:
            email: Email address to remove from bounces

        Returns:
            Deletion response
        """
        try:
            client = self.factory.create_client("sendgrid")
            result = await client.delete_bounce(email)

            self.logger.info(f"Removed {email} from bounce list")
            return result

        except Exception as e:
            self.logger.error(f"Failed to delete bounce: {e}")
            raise

    async def validate_email_address(self, email: str) -> dict[str, Any]:
        """
        Validate an email address using SendGrid

        Args:
            email: Email address to validate

        Returns:
            Validation results
        """
        try:
            client = self.factory.create_client("sendgrid")
            result = await client.validate_email_address(email)

            self.logger.info(f"Email validation completed for {email}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to validate email: {e}")
            raise

    async def get_webhook_stats(self) -> dict[str, Any]:
        """
        Get webhook event statistics from SendGrid

        Returns:
            Webhook statistics
        """
        try:
            client = self.factory.create_client("sendgrid")
            result = await client.get_webhook_stats()

            self.logger.info("Retrieved webhook statistics")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get webhook stats: {e}")
            raise

    # Stripe API Methods
    async def create_checkout_session(
        self,
        price_id: str,
        success_url: str,
        cancel_url: str,
        quantity: int = 1,
        customer_email: str | None = None,
        client_reference_id: str | None = None,
        metadata: dict[str, str] | None = None,
        mode: str = "payment",
    ) -> dict[str, Any]:
        """
        Create a Stripe checkout session with a single price ID

        Args:
            price_id: Stripe price ID
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect after cancelled payment
            quantity: Quantity of items
            customer_email: Pre-fill customer email
            client_reference_id: Reference ID for tracking
            metadata: Additional metadata
            mode: Payment mode (payment, subscription, setup)

        Returns:
            Checkout session data including session ID and URL
        """
        try:
            client = self.factory.create_client("stripe")

            result = await client.create_checkout_session(
                price_id=price_id,
                success_url=success_url,
                cancel_url=cancel_url,
                quantity=quantity,
                customer_email=customer_email,
                client_reference_id=client_reference_id,
                metadata=metadata,
                mode=mode,
            )

            self.logger.info(f"Checkout session created: {result.get('id')}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to create checkout session: {e}")
            raise

    async def create_checkout_session_with_line_items(
        self,
        line_items: list[dict[str, Any]],
        success_url: str,
        cancel_url: str,
        customer_email: str | None = None,
        client_reference_id: str | None = None,
        metadata: dict[str, str] | None = None,
        mode: str = "payment",
        expires_at: int | None = None,
        payment_method_types: list[str] | None = None,
        billing_address_collection: str | None = None,
        allow_promotion_codes: bool | None = None,
    ) -> dict[str, Any]:
        """
        Create a Stripe checkout session with line items (supports dynamic pricing)

        Args:
            line_items: List of line items with price_data or price
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect after cancelled payment
            customer_email: Pre-fill customer email
            client_reference_id: Reference ID for tracking
            metadata: Additional metadata
            mode: Payment mode (payment, subscription, setup)
            expires_at: Unix timestamp when session expires
            payment_method_types: List of payment methods to accept
            billing_address_collection: How to collect billing address
            allow_promotion_codes: Whether to allow promo codes

        Returns:
            Checkout session data including session ID and URL
        """
        try:
            client = self.factory.create_client("stripe")

            result = await client.create_checkout_session_with_line_items(
                line_items=line_items,
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=customer_email,
                client_reference_id=client_reference_id,
                metadata=metadata,
                mode=mode,
                expires_at=expires_at,
                payment_method_types=payment_method_types,
                billing_address_collection=billing_address_collection,
                allow_promotion_codes=allow_promotion_codes,
            )

            self.logger.info(f"Checkout session created: {result.get('id')}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to create checkout session with line items: {e}")
            raise

    async def create_payment_intent(
        self,
        amount: int,
        currency: str = "usd",
        customer_id: str | None = None,
        description: str | None = None,
        metadata: dict[str, str] | None = None,
        receipt_email: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a Stripe payment intent

        Args:
            amount: Amount in cents
            currency: Currency code
            customer_id: Stripe customer ID
            description: Payment description
            metadata: Additional metadata
            receipt_email: Email for receipt

        Returns:
            Payment intent data
        """
        try:
            client = self.factory.create_client("stripe")

            result = await client.create_payment_intent(
                amount=amount,
                currency=currency,
                customer_id=customer_id,
                description=description,
                metadata=metadata,
                receipt_email=receipt_email,
            )

            self.logger.info(f"Payment intent created: {result.get('id')}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to create payment intent: {e}")
            raise

    async def get_checkout_session(self, session_id: str) -> dict[str, Any]:
        """
        Retrieve a checkout session

        Args:
            session_id: Checkout session ID

        Returns:
            Checkout session data
        """
        try:
            client = self.factory.create_client("stripe")
            result = await client.get_checkout_session(session_id)

            self.logger.info(f"Retrieved checkout session: {session_id}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get checkout session: {e}")
            raise

    async def get_payment_intent(self, payment_intent_id: str) -> dict[str, Any]:
        """
        Retrieve a payment intent

        Args:
            payment_intent_id: Payment intent ID

        Returns:
            Payment intent data
        """
        try:
            client = self.factory.create_client("stripe")
            result = await client.get_payment_intent(payment_intent_id)

            self.logger.info(f"Retrieved payment intent: {payment_intent_id}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get payment intent: {e}")
            raise

    async def create_customer(
        self,
        email: str,
        name: str | None = None,
        description: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Create a Stripe customer

        Args:
            email: Customer email
            name: Customer name
            description: Customer description
            metadata: Additional metadata

        Returns:
            Customer data
        """
        try:
            client = self.factory.create_client("stripe")

            result = await client.create_customer(email=email, name=name, description=description, metadata=metadata)

            self.logger.info(f"Customer created: {result.get('id')}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to create customer: {e}")
            raise

    async def get_customer(self, customer_id: str) -> dict[str, Any]:
        """
        Retrieve a customer

        Args:
            customer_id: Stripe customer ID

        Returns:
            Customer data
        """
        try:
            client = self.factory.create_client("stripe")
            result = await client.get_customer(customer_id)

            self.logger.info(f"Retrieved customer: {customer_id}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get customer: {e}")
            raise

    async def create_product(
        self,
        name: str,
        description: str | None = None,
        metadata: dict[str, str] | None = None,
        active: bool = True,
    ) -> dict[str, Any]:
        """
        Create a Stripe product

        Args:
            name: Product name
            description: Product description
            metadata: Additional metadata
            active: Whether product is active

        Returns:
            Product data including product ID
        """
        try:
            client = self.factory.create_client("stripe")

            result = await client.create_product(name=name, description=description, metadata=metadata, active=active)

            self.logger.info(f"Product created: {result.get('id')}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to create product: {e}")
            raise

    async def list_charges(
        self,
        customer_id: str | None = None,
        limit: int = 10,
        starting_after: str | None = None,
    ) -> dict[str, Any]:
        """
        List charges

        Args:
            customer_id: Filter by customer ID
            limit: Number of charges to return
            starting_after: Pagination cursor

        Returns:
            List of charges
        """
        try:
            client = self.factory.create_client("stripe")

            result = await client.list_charges(customer_id=customer_id, limit=limit, starting_after=starting_after)

            self.logger.info(f"Listed charges: {result.get('data', []).__len__()} charges")
            return result

        except Exception as e:
            self.logger.error(f"Failed to list charges: {e}")
            raise

    async def create_price(
        self,
        amount: int,
        currency: str = "usd",
        product_id: str | None = None,
        product_data: dict[str, str] | None = None,
        recurring: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a price

        Args:
            amount: Price amount in cents
            currency: Currency code
            product_id: Existing product ID
            product_data: New product data
            recurring: Recurring billing configuration

        Returns:
            Price data
        """
        try:
            client = self.factory.create_client("stripe")

            result = await client.create_price(
                amount=amount,
                currency=currency,
                product_id=product_id,
                product_data=product_data,
                recurring=recurring,
            )

            self.logger.info(f"Price created: {result.get('id')}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to create price: {e}")
            raise

    async def create_webhook_endpoint(
        self, url: str, enabled_events: list[str], description: str | None = None
    ) -> dict[str, Any]:
        """
        Create a webhook endpoint

        Args:
            url: Webhook URL
            enabled_events: List of events to listen for
            description: Webhook description

        Returns:
            Webhook endpoint data
        """
        try:
            client = self.factory.create_client("stripe")

            result = await client.create_webhook_endpoint(
                url=url, enabled_events=enabled_events, description=description
            )

            self.logger.info(f"Webhook endpoint created: {result.get('id')}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to create webhook endpoint: {e}")
            raise

    async def construct_webhook_event(self, payload: str, signature: str, endpoint_secret: str) -> dict[str, Any]:
        """
        Verify and construct webhook event

        Args:
            payload: Raw webhook payload
            signature: Webhook signature
            endpoint_secret: Webhook endpoint secret

        Returns:
            Webhook event data
        """
        try:
            client = self.factory.create_client("stripe")

            result = await client.construct_webhook_event(
                payload=payload, signature=signature, endpoint_secret=endpoint_secret
            )

            self.logger.info(f"Webhook event constructed: {result.get('type')}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to construct webhook event: {e}")
            raise

    # Combined Workflow Methods
    async def complete_business_analysis(
        self,
        business_id: str,
        business_url: str | None = None,
        include_email_generation: bool = False,
    ) -> dict[str, Any]:
        """
        Complete analysis workflow: PageSpeed → AI insights

        Args:
            business_id: Business ID
            business_url: Business website URL
            include_email_generation: Whether to generate email content

        Returns:
            Complete analysis results
        """
        analysis_results = {
            "business_id": business_id,
            "business_data": None,
            "website_analysis": None,
            "ai_insights": None,
            "email_content": None,
            "errors": [],
        }

        try:
            # Step 1: Check website URL
            if not business_url:
                analysis_results["errors"].append("No website URL provided")
                return analysis_results

            website_url = business_url

            # Step 2: Analyze website with PageSpeed
            try:
                website_analysis = await self.analyze_website(website_url)
                analysis_results["website_analysis"] = website_analysis

                # Step 3: Generate AI insights
                try:
                    # Use business_id as name since we don't have business data
                    business_context = {
                        "name": business_id,
                        "categories": [],
                        "location": {},
                    }

                    ai_insights = await self.generate_website_insights(website_analysis, business_context)
                    analysis_results["ai_insights"] = ai_insights

                    # Step 4: Generate email content if requested
                    if include_email_generation and ai_insights.get("ai_recommendations"):
                        try:
                            email_content = await self.generate_personalized_email(
                                business_name=business_id,
                                website_issues=ai_insights["ai_recommendations"],
                                recipient_name=None,
                            )
                            analysis_results["email_content"] = email_content

                        except Exception as e:
                            analysis_results["errors"].append(f"Email generation failed: {e}")

                except Exception as e:
                    analysis_results["errors"].append(f"AI insights failed: {e}")

            except Exception as e:
                analysis_results["errors"].append(f"Website analysis failed: {e}")

        except Exception as e:
            analysis_results["errors"].append(f"Business lookup failed: {e}")

        self.logger.info(f"Complete analysis finished for {business_id}")
        return analysis_results

    # Gateway Management Methods
    def get_gateway_status(self) -> dict[str, Any]:
        """
        Get comprehensive gateway status

        Returns:
            Gateway status information
        """
        try:
            # Get factory status
            factory_status = self.factory.get_client_status()

            # Get health check
            health_status = self.factory.health_check()

            # Get metrics summary
            metrics_summary = self.metrics.get_metrics_summary()

            return {
                "status": "operational",
                "factory": factory_status,
                "health": health_status,
                "metrics": metrics_summary,
                "facade_version": "1.0.0",
            }

        except Exception as e:
            self.logger.error(f"Failed to get gateway status: {e}")
            return {"status": "error", "error": str(e)}

    async def get_all_rate_limits(self) -> dict[str, Any]:
        """
        Get rate limit status for all providers

        Returns:
            Rate limit information for all providers
        """
        rate_limits = {}

        for provider in self.factory.get_provider_names():
            try:
                client = self.factory.create_client(provider)
                rate_limits[provider] = client.get_rate_limit()
            except Exception as e:
                rate_limits[provider] = {"error": str(e)}

        return rate_limits

    async def calculate_total_costs(self) -> dict[str, Decimal]:
        """
        Calculate total costs across all providers

        Returns:
            Cost breakdown by provider
        """
        costs = {}

        for provider in self.factory.get_provider_names():
            try:
                self.factory.create_client(provider)
                # This would typically query metrics for actual costs
                # For now, return estimated costs
                costs[provider] = Decimal("0.00")
            except Exception as e:
                self.logger.error(f"Failed to get costs for {provider}: {e}")
                costs[provider] = Decimal("0.00")

        return costs

    def invalidate_all_caches(self) -> None:
        """Invalidate all cached clients and responses"""
        self.factory.invalidate_cache()
        self.logger.info("All caches invalidated")


# Global facade instance
_facade_instance = None


def get_gateway_facade() -> GatewayFacade:
    """
    Get the global gateway facade instance

    Returns:
        GatewayFacade instance
    """
    global _facade_instance
    if _facade_instance is None:
        _facade_instance = GatewayFacade()
    return _facade_instance
