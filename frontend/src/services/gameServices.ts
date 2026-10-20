import { request } from '@umijs/max';
export type Policy = {
  ReturnRecipient?: string;
  ReturnPhone?: string;
  ReturnAddress?: string;
  RentalEnabled: boolean;
  PurchaseEnabled: boolean;
  MinDays: number;
  MaxDays: number;
  MaxQuantity: number;
  AdvanceDays: number;
  Discounts: { MinDays: number; Percent: number }[];
  Pickup: boolean;
  Shipping: boolean;
  ShippingServices?: string[];
  RentalTerms: string;
  PurchaseTerms: string;
  ContactNotice: string;
  QualityRewardPoints: number;
};
export type Stock = {
  ID: number;
  StoreID: number;
  BoardGameID: number;
  Kind: string;
  Condition: string;
  Description: string;
  Enabled: boolean;
  Quantity: number;
  Reserved: number;
  Out: number;
  Held: number;
  Price: number;
  Deposit: number;
  Version: number;
};
export type Line = {
  Bought: number;
  ID: number;
  StockID: number;
  BoardGameID: number;
  GameName: string;
  CoverURL: string;
  Condition: string;
  Description: string;
  Quantity: number;
  UnitPrice: number;
  Deposit: number;
  ServiceAmount: number;
  Returned: number;
  Inspected: number;
  Damaged: number;
  Lost: number;
};
export type Order = {
  ReturnMethod?: "pickup" | "shipping" | "";
  ReturnRequestedAt?: string;
  ReturnTrackingCompany?: string;
  ReturnTrackingNumber?: string;
  ParentOrderID?: number;
  DepositApplied: number;
  ContactName: string;
  ContactPhone: string;
  ID: number;
  RequestedStoreID: number;
  AcceptedStoreID?: number;
  Kind: string;
  Status: string;
  Amount: number;
  ServiceAmount: number;
  DepositAmount: number;
  DepositRetained: number;
  AutoRefund?: boolean;
  RefundAmount: number;
  DeliveryMethod: string;
  StartDate: string;
  EndDate: string;
  Days: number;
  Terms: string;
  Remark: string;
  TrackingCompany: string;
  TrackingNumber: string;
  Version: number;
  CreatedAt: string;
  PaidAt?: string;
  AcceptedAt?: string;
  PaymentExpiresAt?: string;
  FulfilledAt?: string;
  CompletedAt?: string;
  Lines: Line[];
};
export type OrderDetail = {
  Order: Order;
  Contact: { Name: string; Phone: string; Address: string; ShippingService?: string };
  Refunds: {
    ID: number;
    Amount: number;
    Status: string;
    ReviewRemark?: string;
    RefundError?: string;
  }[];
  Journal: {
    ID: number;
    Action: string;
    Actor: string;
    Remark: string;
    CreatedAt: string;
    ServiceAmount: number;
    DepositAmount: number;
  }[];
};
export type Share = {
  GameName: string;
  StoreName: string;
  ID: number;
  BoardGameID: number;
  StoreID: number;
  Content: string;
  Images: string[];
  Status: string;
  Quality: boolean;
  RewardPoints: number;
  RewardedAt?: string;
  Version: number;
  CreatedAt: string;
  Author: { UserID: number; NickName?: string; Avatar?: string };
};
export type Lead = {
  StoreID: number;
  StoreName: string;
  ID: number;
  GameID: number;
  GameName: string;
  UserID: number;
  NickName?: string;
  Avatar?: string;
  Phone: string;
  UpdatedAt: string;
};
export { newRequestKey } from './requestKey';
export const money = (v: number) => `¥${(v / 100).toFixed(2)}`;
export const states: Record<string, string> = {
  pending_confirm: '待门店确认',
  awaiting_payment: '待付款',
  pending_accept: '待门店接单',
  accepted: '待交付',
  rented: '出租中',
  inspection: '归还待检查',
  completed: '已完成',
  refund_pending: '待退款',
  refunded: '已退款',
  cancelled: '已取消',
};
export const actions: Record<string, string> = {
  return_complete: '确认完好归还并退押金',
  request_return: '申请归还',
  buyout: '租转购',
  service_paid: '租金／货款收款',
  deposit_paid: '押金收款',
  accept: '确认订单',
  reject: '拒单',
  cancel: '取消',
  dispatch: '确认交付',
  return: '登记归还',
  inspect: '检查配件与品相',
  declare_loss: '登记整盒遗失',
  purchase_return: '登记购买退回',
  settle_deposit: '结算押金',
  refund: '退款确认',
  adjust: '库存调整',
};
export async function call<T>(
  path: string,
  method = 'GET',
  data?: unknown,
  storeID?: number,
) {
  const res = await request<API.Response<T>>(
    `/admin_api/game-service/v1/${path}`,
    {
      method,
      ...(method === 'GET' ? { params: data } : { data }),
      timeout: 30000,
      ...(storeID ? { headers: { 'X-Store-ID': String(storeID) } } : {}),
    },
  );
  if (res.Code !== 0) throw Error(res.Message || res.Msg || '操作失败');
  return res.Data as T;
}

export type Inventory = {
  ID: number;
  BoardGameID: number;
  Total: number;
  Quantity: number;
  Available: number;
  Reserved: number;
  Out: number;
  Held: number;
  Version: number;
  RentalEnabled: boolean;
  PurchaseEnabled: boolean;
  BuyoutEnabled: boolean;
  RentalPrice: number;
  Deposit: number;
  PurchasePrice: number;
  Condition: string;
  Description: string;
  Legacy: boolean;
  MultipleOffers: boolean;
};
export const gameInventories = () => call<Inventory[]>('inventory');
export const saveGameInventories = (
  Items: (Inventory & { RequestKey: string })[],
) => call('inventory', 'PUT', { Items });
