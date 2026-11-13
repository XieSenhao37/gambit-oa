import { request } from '@umijs/max';
export { newRequestKey } from './requestKey';
export const money = (n: number) => `¥${(n / 100).toFixed(2)}`;
export const statuses: Record<string, string> = {
  awaiting_payment: '待付款',
  closing: '取消确认中',
  cancelled: '已取消',
  paid: '待交付',
  shipped: '待收货',
  completed: '已完成',
  refunded: '已退款',
};
export const afterSaleStatuses: Record<string, string> = {
  pending_review: '待审核',
  rejected: '已拒绝',
  awaiting_return: '待退货',
  returning: '待验收',
  refund_pending: '退款处理中',
  completed: '售后完成',
};
export interface Category {
  ID: number;
  ParentID: number;
  Name: string;
  Sort: number;
  Enabled: boolean;
  Version: number;
}
export interface SKU {
  ID: number;
  Name: string;
  Code: string;
  Image: string;
  Specifications: Record<string, string>;
  Enabled: boolean;
  StockID: number;
  Price: number;
  Available: number;
  OnSale: boolean;
  Version: number;
}
export interface Product {
  ID: number;
  CategoryID: number;
  Name: string;
  Images: string[];
  Description: string;
  Parameters: Record<string, string>;
  Enabled: boolean;
  Sort: number;
  Version: number;
  Offers: SKU[];
}
export interface Policy {
  StoreID: number;
  Enabled: boolean;
  Pickup: boolean;
  Shipping: boolean;
  ShippingServices: string[];
  Terms: string;
  ReturnName: string;
  ReturnPhone: string;
  ReturnAddress: string;
  Version: number;
}
export interface CouponTemplate {
  ID: number;
  Name: string;
  Amount: number;
  Minimum: number;
  ProductIDs: number[];
  StartsAt: string;
  EndsAt: string;
  Enabled: boolean;
  Claimable: boolean;
  TotalLimit: number;
  PerUserLimit: number;
  Issued: number;
  Version: number;
}
export interface Line {
  ID: number;
  ProductName: string;
  SKUName: string;
  Quantity: number;
  UnitPrice: number;
  Amount: number;
  Discount: number;
  RefundedQuantity: number;
  RefundedAmount: number;
  Image: string;
}
export interface Order {
  ID: number;
  StoreID: number;
  Status: string;
  Subtotal: number;
  Discount: number;
  Amount: number;
  Refunded: number;
  Version: number;
  DeliveryMethod: string;
  TrackingNumber: string;
  PickupCode: string;
  Remark: string;
  Terms: string;
  CreatedAt: string;
  ExpiresAt: string;
  Lines: Line[];
}
export interface AfterSale {
  ID: number;
  OrderID: number;
  Kind: string;
  Status: string;
  Reason: string;
  ReviewNote: string;
  TrackingCompany: string;
  TrackingNumber: string;
  Amount: number;
  Version: number;
  RefundRequestID?: number;
  Lines: {
    ID: number;
    OrderLineID: number;
    Quantity: number;
    Amount: number;
    Restock: boolean;
  }[];
}
export interface OrderDetail {
  Order: Order;
  Contact: {
    Name: string;
    Phone: string;
    Address: string;
    ShippingService: string;
  };
  AfterSales: AfterSale[];
  Refunds: {
    ID: number;
    Status: string;
    Amount: number;
    RefundError?: string;
  }[];
}
export async function call<T>(
  path: string,
  method = 'GET',
  data?: object
): Promise<T> {
  const res = await request<{
    Code: number;
    Data: T;
    Message?: string;
    Msg?: string;
  }>(`/admin_api/retail/v1/${path}`, {
    method,
    ...(method === 'GET' ? { params: data } : { data }),
  });
  if (res.Code !== 0) throw Error(res.Message || res.Msg || '操作失败');
  return res.Data;
}
