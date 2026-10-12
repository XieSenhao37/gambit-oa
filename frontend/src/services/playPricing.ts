import { request } from '@umijs/max';
export type Price = {
  Price: number;
  AdditionPrice: number;
  MaxHour: number;
  MaxTotal: number;
  BundlePricing?: boolean;
};
export type Schedule = {
  Common: Price;
  Holiday: Price;
  UseAdjustedWorkdays?: boolean;
  HolidayWeekdays?: number[];
  DateTypes?: Record<string, string>;
  SpecialMap?: Record<string, Price>;
  TimeRules?: {
    Name: string;
    StartDate: string;
    EndDate: string;
    StartTime: string;
    EndTime: string;
    DayType: string;
    Price: Price;
  }[];
};
export type PricingData = {
  Config: Schedule | null;
  Revision: string;
  Calendar: {
    Year: number;
    Source: string;
    Holidays: { Name: string; Start: string; End: string }[];
    Workdays: string[];
  };
};
export const getPricing = () =>
  request<API.Response<PricingData>>('/admin_api/play-pricing/v1');
export const savePricing = (Config: Schedule, Revision: string) =>
  request<API.Response<PricingData>>('/admin_api/play-pricing/v1', {
    method: 'PUT',
    data: { Config, Revision },
  });
export const previewPricing = (
  Config: Schedule,
  InTime: string,
  Hours: number,
) =>
  request<API.Response<{ Amount: number; Rule: string; DayType: string }>>(
    '/admin_api/play-pricing/v1/preview',
    { method: 'POST', data: { Config, InTime, Hours } },
  );
