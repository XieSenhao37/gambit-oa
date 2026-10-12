import type { Price, Schedule } from '@/services/playPricing';
export type PriceMode = 'daily_cap' | 'bundle' | 'legacy';
export type FormPrice = Price & { Mode: PriceMode };
export const defaultWeekdays = [0, 5, 6];
export const emptyPrice: FormPrice = {
  Price: 0,
  AdditionPrice: 0,
  MaxHour: 3,
  MaxTotal: 0,
  BundlePricing: true,
  Mode: 'bundle',
};
export function fromPrice(price: Price): FormPrice {
  const Mode =
    price.AdditionPrice === 0
      ? 'daily_cap'
      : price.BundlePricing || price.MaxTotal <= price.Price * price.MaxHour
      ? 'bundle'
      : 'legacy';
  return {
    ...price,
    Mode,
    Price: price.Price / 100,
    MaxTotal: price.MaxTotal / 100,
    AdditionPrice: price.AdditionPrice / 100,
  };
}
export function toPrice(price: FormPrice): Price {
  return {
    Price: Math.round(price.Price * 100),
    MaxTotal: Math.round(price.MaxTotal * 100),
    MaxHour: price.Mode === 'daily_cap' ? 3 : price.MaxHour,
    AdditionPrice:
      price.Mode === 'daily_cap' ? 0 : Math.round(price.AdditionPrice * 100),
    BundlePricing: price.Mode === 'bundle',
  };
}
export function priceTotal(price: Price, hours: number): number {
  const baseHours = price.BundlePricing
    ? Math.min(hours, price.MaxHour)
    : hours;
  return (
    Math.min(price.MaxTotal, baseHours * price.Price) +
    Math.max(0, hours - price.MaxHour) * price.AdditionPrice
  );
}
export function fromSchedule(schedule: Schedule | null) {
  const s = schedule ?? {
    Common: toPrice(emptyPrice),
    Holiday: toPrice(emptyPrice),
  };
  return {
    ...s,
    Common: fromPrice(s.Common),
    Holiday: fromPrice(s.Holiday),
    HolidayWeekdays: s.HolidayWeekdays ?? defaultWeekdays,
    UseAdjustedWorkdays: s.UseAdjustedWorkdays ?? true,
    TimeRules: (s.TimeRules ?? []).map((r) => ({
      ...r,
      Price: fromPrice(r.Price),
    })),
    DateOverrides: Object.entries(s.DateTypes ?? {}).map(([Date, DayType]) => ({
      Date,
      DayType,
    })),
    Specials: Object.entries(s.SpecialMap ?? {}).map(([Date, Price]) => ({
      Date,
      Price: fromPrice(Price),
    })),
  };
}
export function toSchedule(values: any): Schedule {
  const dates = values.DateOverrides ?? [],
    specials = values.Specials ?? [];
  for (const list of [dates, specials])
    if (new Set(list.map((r: any) => r.Date)).size !== list.length)
      throw Error('指定日期不能重复');
  return {
    Common: toPrice(values.Common),
    Holiday: toPrice(values.Holiday),
    HolidayWeekdays: values.HolidayWeekdays ?? defaultWeekdays,
    UseAdjustedWorkdays: !!values.UseAdjustedWorkdays,
    TimeRules: (values.TimeRules ?? []).map((r: any) => ({
      ...r,
      StartDate: r.StartDate || '',
      EndDate: r.EndDate || '',
      Price: toPrice(r.Price),
    })),
    DateTypes: Object.fromEntries(dates.map((r: any) => [r.Date, r.DayType])),
    SpecialMap: Object.fromEntries(
      specials.map((r: any) => [r.Date, toPrice(r.Price)]),
    ),
  };
}
export const regularDraft = {
  Common: fromPrice({
    Price: 2800,
    MaxTotal: 7800,
    MaxHour: 3,
    AdditionPrice: 0,
  }),
  Holiday: fromPrice({
    Price: 2800,
    MaxTotal: 7800,
    MaxHour: 3,
    AdditionPrice: 1000,
    BundlePricing: true,
  }),
  HolidayWeekdays: defaultWeekdays,
  UseAdjustedWorkdays: true,
};
