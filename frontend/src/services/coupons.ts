import { request } from '@umijs/max';

export type ActivityStatus = 'scheduled' | 'active' | 'ended';

export interface CouponTerms {
  ActivityName: string;
  Title: string;
  CouponType: number;
  Amount: number;
  MinimumAmount: number;
  Expire: number;
  StartDate: string;
  EndDate: string;
  ApplicableScenes: number[] | null;
  CanReReceive: number;
  Description: string | null;
}

export interface CouponActivity extends CouponTerms {
  ID: number;
  Count: number;
  ControlRoles: number[];
  Status: ActivityStatus;
  Revision: string;
  Issued: number;
  Used: number;
  Reserved: number;
  Available: number;
  TermsLocked: boolean;
  SystemLocked: boolean;
}

export interface CouponRecord {
  ID: number;
  UserID: number | null;
  NickName: string | null;
  Source: string;
  Status: string;
  ReceivedAt: string;
  ExpireAt: string | null;
  UsedAt: string | null;
}

export interface CouponFilters {
  Page: number;
  Keyword?: string;
  Status?: ActivityStatus;
}

interface PageResult<T> {
  Items: T[];
  Total: number;
}

async function call<T>(
  path: string,
  method: 'GET' | 'POST' | 'PUT',
  values: object,
) {
  const result = await request<{ Code: number; Data: T; Message?: string }>(
    `/admin_api/coupon/v1/activities${path}`,
    { method, ...(method === 'GET' ? { params: values } : { data: values }) },
  );
  if (result.Code !== 0) throw new Error(result.Message || '操作失败');
  return result.Data;
}

export const listCouponActivities = (query: CouponFilters) =>
  call<PageResult<CouponActivity>>('', 'GET', query);

export const saveCouponActivity = (
  id: number | undefined,
  data: Pick<CouponActivity, 'Count' | 'ControlRoles'> &
    Partial<CouponTerms & Pick<CouponActivity, 'Revision'>>,
) =>
  call<{ ID: number }>(
    id === undefined ? '' : `/${id}`,
    id === undefined ? 'POST' : 'PUT',
    data,
  );

export const listCouponRecords = (id: number, page: number) =>
  call<PageResult<CouponRecord>>(`/${id}/records`, 'GET', { Page: page });
