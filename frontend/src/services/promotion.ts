import { request } from '@umijs/max';
export type DisplayFrequency = 'daily' | 'entry';
export interface PopupImage {
  Id: string;
  Title: string;
  Img: string;
  Enabled: boolean;
  Sort: number;
}
export interface HomePromotions {
  Splash: {
    Title: string;
    Img: string;
    Enabled: boolean;
    Frequency: DisplayFrequency;
    Seconds: number;
  };
  Popup: { Enabled: boolean; Frequency: DisplayFrequency; Items: PopupImage[] };
}
export interface PromotionResponse {
  Config: HomePromotions;
  Revision: string;
}
const path = '/admin_api/promotion/v1';
export async function getPromotions(): Promise<PromotionResponse> {
  const r = await request(path);
  if (r.Code !== 0) throw new Error(r.Message);
  return r.Data;
}
export async function savePromotions(
  Config: HomePromotions,
  Revision: string,
): Promise<PromotionResponse> {
  const r = await request(path, { method: 'PUT', data: { Config, Revision } });
  if (r.Code !== 0) throw new Error(r.Message);
  return r.Data;
}
