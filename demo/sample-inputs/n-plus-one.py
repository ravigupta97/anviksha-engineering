# demo/sample-inputs/n-plus-one.py
# Demo input — deliberately vulnerable code for Anviksha showcase

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Order, OrderItem

class OrderProcessingController:
    """Controller class handling user order transaction history queries."""
    
    async def get_user_orders_metadata(self, session: AsyncSession, user_id: int):
        """Fetches transactions linked to a user.
        
        DELIBERATE ISSUES INCLUDED:
        1. Performance (N+1 Query Bottleneck): The script performs a select query to fetch
           orders, then executes a nested query *inside a loop* to load items for every single order.
           For 100 orders, this executes 101 separate database roundtrips.
        2. Architectural Violation: Mixing raw database queries directly inside a Controller class,
           violating the Repository Pattern separation.
        """
        # Step 1: Query user orders
        orders_query = select(Order).where(Order.user_id == user_id)
        result = await session.execute(orders_query)
        orders = result.scalars().all()

        orders_payload = []
        
        # Step 2: N+1 loop executing nested queries inside loop
        for order in orders:
            # Fatal N+1 subquery roundtrip
            items_query = select(OrderItem).where(OrderItem.order_id == order.id)
            items_result = await session.execute(items_query)
            items = items_result.scalars().all()
            
            orders_payload.append({
                "order_id": order.id,
                "total": order.total,
                "items_count": len(items)
            })

        return orders_payload
