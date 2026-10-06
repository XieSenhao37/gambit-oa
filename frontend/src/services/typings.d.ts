declare namespace API {
  interface StoreInfo {
    Id: number;
    Code: string;
    Name: string;
    Status: number;
    Sort: number;
    Address?: string;
  }

  // 用户相关
  interface UserInfo {
    Id: number;
    OpenId: string;
    UserType: number;
    Role: 0 | 1 | 2 | 125 | 126 | 127; // 0-普通用户，1-店员，2-兼职，125-店长，126-管理员，127-超级管理员
    NickName: string;
    Gender: 0 | 1 | 2; // 0-未知，1-男性，2-女性
    avatar: string;
    birthDay: string;
    PhoneNumber: string;
    phoneNumberChangeTime: string;
    monthCardId?: number;
    partnerId?: number;
    MonthCardExpire?: string;
    PointBalance: number;
    WalletBalance: number;
    TotalConsumptionAmount: number;
    createdAt: string;
    updatedAt: string;
  }

  // 桌游相关
  interface BoardGame {
    id: number;
    name: string;
    coverUrl: string;
  }

  // 订单相关
  interface PlayOrder {
    Id: number;
    StoreId?: number;
    OpenId: string;
    InTime: string;
    OutTime?: string;
    PlayTime?: number;
    UnitPrice?: number;
    Amount?: number;
    SettleStatus: 0 | 1; // 0-待结算，1-已结算
    Comment?: string;
    CreatedAt: string;
    UpdatedAt: string;
    User?: {
      Id: number;
      OpenId: string;
      NickName: string;
      Phone?: string | null;
    };
  }

  type PlayWorkbenchStatus = 'pending' | 'payment_pending' | 'settled';

  interface PlayWorkbenchOrder {
    ID: number;
    StoreID: number;
    OpenID: string;
    UserID?: number | null;
    NickName?: string | null;
    Phone?: string | null;
    InTime: number;
    OutTime?: number | null;
    PlayHours: number;
    TheoreticalAmount: number;
    SettledAmount: number;
    SettleStatus: 0 | 1;
    PaymentPending: boolean;
    Comment?: string | null;
  }

  interface PlayWorkbenchRecentGroup {
    ID: string;
    WindowStart: number;
    WindowEnd: number;
    OrderCount: number;
    MinPlayHours: number;
    MaxPlayHours: number;
    TheoreticalTotalAmount: number;
    SettledTotalAmount: number;
    Orders: PlayWorkbenchOrder[];
  }

  interface PlayWorkbenchData {
    Orders: PlayWorkbenchOrder[];
    RecentGroups: PlayWorkbenchRecentGroup[];
    RefreshedAt: number;
  }

  interface SettlePlayWorkbenchRequest {
    Amount: number;
    Comment?: string;
  }

  interface SettlePlayWorkbenchResult {
    PlayOrderID: number;
    PayOrderID: number;
    OutTime: number;
    PlayHours: number;
    Amount: number;
  }

  // 分页请求参数
  interface PageParams {
    current?: number;
    pageSize?: number;
  }

  // 通用响应格式
  interface Response<T = any> {
    Code: number;
    Msg: string;
    Message?: string;
    Data?: T;
  }

  // 分页响应格式
  interface PageData<T> {
    Items: T[];
    Total: number;
    CurrentPage: number;
    PageSize: number;
  }

  // 批量操作请求
  interface BatchOperationRequest {
    ids: number[];
  }

  // 用户角色更新请求
  interface UpdateUserRoleRequest {
    role: 0 | 1 | 2 | 126 | 127;
  }

  // 订单查询参数
  interface QueryOrdersParams {
    current?: number;
    pageSize?: number;
    UserId?: number;
    OpenId?: string;
    SettleStatus?: 0 | 1;
    StartTime?: string;
    EndTime?: string;
    // 添加入场时间和出场时间的范围筛选
    InTimeStart?: string;
    InTimeEnd?: string;
    OutTimeStart?: string;
    OutTimeEnd?: string;
  }

  // 用户查询参数
  interface QueryUsersParams {
    Current?: number;
    PageSize?: number;
    Id?: number;
    OpenId?: string;
    Role?: number;
    UserType?: number;
    NickName?: string;
    PhoneNumber?: string;
    IsMonthCardUser?: string; // 添加月卡用户筛选参数，'1'表示是，'0'表示否
    SortField?: 'PointBalance' | 'WalletBalance' | 'TotalConsumptionAmount';
    SortOrder?: 'asc' | 'desc';
  }

  // 用户更新请求
  interface UpdateUserRequest {
    Role: number;
  }

  type MonthCardSource =
    | 'wechat'
    | 'third_party'
    | 'gift'
    | 'meituan'
    | 'storage_gift'
    | 'manual_adjustment'
    | 'other';

  interface MonthCardOrderItem {
    Id: number;
    OpenId: string;
    UserId?: number | null;
    NickName?: string;
    PhoneNumber?: string | null;
    OpenPeriod: number;
    DurationDays: number;
    UnitPrice: number;
    FundingType: string;
    Amount: number;
    OpenType: number;
    SettleStatus: number;
    Source: MonthCardSource;
    SourceText: string;
    Operator?: string;
    ExternalNo?: string;
    StoreId?: number | null;
    EffectiveAt?: string | null;
    Remark?: string;
    CreatedAt?: string | null;
    UpdatedAt?: string | null;
  }

  interface QueryMonthCardOrdersParams {
    Current?: number;
    PageSize?: number;
    UserId?: number;
    OpenId?: string;
    Source?: MonthCardSource;
    ExternalNo?: string;
    StartTime?: string;
    EndTime?: string;
  }

  // 查询桌游列表参数
  interface QueryGamesParams {
    PageNum?: number;
    PageSize?: number;
    Keyword?: string;
  }

  // 餐饮制作台
  interface CateringOrderItem {
    Id: number;
    DishName: string;
    Count: number;
    TotalPrice: number;
    Selections?: any;
    SelectionsText?: string;
  }

  interface CateringOrder {
    Id: number;
    StoreId?: number;
    Code: string;
    OpenId: string;
    Status: 0 | 1 | 2;
    SettleStatus: number;
    Takeaway: boolean;
    TotalPrice: number;
    Comment?: string;
    CreatedAt: string;
    UpdatedAt?: string;
    WaitingMinutes: number;
    ReadyMinutes?: number;
    TableInfo?: {
      Id: number;
      Name: string;
      Area: number;
    };
    User?: {
      Id: number;
      NickName?: string;
      Phone?: string;
    };
    PayOrder?: {
      Id: number;
      OrderId?: string;
      PayStatus: number;
      PayType: number;
      Amount?: number;
      WalletAmount?: number;
      WechatAmount?: number;
      DiscountAmount?: number | null;
      TotalAmount?: number | null;
      RefundAmount?: number | null;
      Description?: string | null;
      ExpireTime?: string | null;
      PayEndTime?: string;
      CreatedAt?: string | null;
      UpdatedAt?: string | null;
    };
    Items: CateringOrderItem[];
  }

  interface QueryCateringOrdersParams {
    current?: number;
    pageSize?: number;
    Status?: 0 | 1 | 2;
    Keyword?: string;
    OnlyToday?: '0' | '1';
    StoreID?: number;
  }

  interface QueryCateringHistoryParams {
    current?: number;
    pageSize?: number;
    Keyword?: string;
    Status?: 0 | 1 | 2;
    PayStatus?: 0 | 1 | 2 | 3 | 'none';
    StartTime?: string;
    EndTime?: string;
  }

  interface FinishCateringOrderResult {
    CateringID: number;
    Status: number;
    AlreadyFinish: boolean;
    NotifySent?: boolean;
    NotifyError?: string;
  }

  type RefundRequestStatus =
    | 'pending_review'
    | 'approved'
    | 'rejected'
    | 'refunding'
    | 'refunded'
    | 'refund_failed';

  type RefundOrderType = 'play' | 'catering' | 'organization';

  interface RefundRequest {
    Id: number;
    OrderType: RefundOrderType;
    OrderId: number;
    PayOrderId: number;
    Amount: number;
    Status: RefundRequestStatus;
    OutRefundNo?: string;
    WxRefundId?: string;
    ReviewRemark?: string;
    RefundError?: string;
    CreatedAt: string;
    UpdatedAt?: string;
    ReviewedAt?: string;
    RefundedAt?: string;
    User?: {
      Id: number;
      NickName?: string;
      Phone?: string;
    };
    PayOrder?: {
      Id: number;
      OrderId?: string;
      PayStatus: number;
      PayType: number;
      PayEndTime?: string;
      GroupActivityParticipantId?: number;
    };
    OrderSnapshot?: {
      TypeText: string;
      StatusText: string;
      Title: string;
      Amount: number;
      CreatedAt?: string;
      ActivityId?: number;
      ActivityTitle?: string;
      StoreId?: number;
      StoreName?: string;
      ActivityStartTime?: string;
      RegistrationStatus?: number;
    };
  }

  interface QueryRefundRequestsParams {
    current?: number;
    pageSize?: number;
    Status?: RefundRequestStatus;
    OrderType?: RefundOrderType;
    Keyword?: string;
  }

  interface RejectRefundRequestParams {
    Remark: string;
  }

  // 桌游信息
  interface BoardGame {
    Id: number;
    StoreId?: number;
    Name: string;
    GstoneScore?: number;
    GstoneRank?: number;
    SupportedPlayers?: number[];
    RecommendedPlayers?: number[];
    CoverUrl: string;
    Complexity?: number;
    PlayTime?: number;
    SetupTime?: string;
    LanguageLevel?: string;
    Description?: string;
    PictureList?: string[];
    Designer?: string[];
    Publisher?: string[];
    PublishLanguage?: string[];
    PublishYear?: number;
    Categories?: string[];
    Modes?: string[];
    Mechanisms?: string[];
    Themes?: string[];
    TableRequirement?: string;
    Portability?: string;
    SuitableAge?: string;
    Count: number;
    CreatedAt: string;
    UpdatedAt: string;
  }

  interface SaveBoardGameParams {
    Name: string;
    GstoneScore?: number;
    GstoneRank?: number;
    SupportedPlayers: number[];
    RecommendedPlayers: number[];
    CoverUrl: string;
    Complexity: number;
    PlayTime: number;
    SetupTime?: string;
    LanguageLevel?: string;
    Description: string;
    PictureList?: string[];
    Designer?: string[];
    Publisher?: string[];
    PublishLanguage?: string[];
    PublishYear?: number;
    Categories?: string[];
    Modes?: string[];
    Mechanisms?: string[];
    Themes?: string[];
    TableRequirement?: string;
    Portability?: string;
    SuitableAge?: string;
  }

  interface SaveGameInventoryParams {
    BoardGameId: number;
    Count: number;
  }

  interface UpdateGameInventoryParams {
    Count: number;
  }

  // 餐品管理
  interface DishCategory {
    Id: number;
    StoreId?: number;
    Name: string;
    Sort: number;
  }

  interface DishOptionItem {
    Name?: string;
    Price?: number;
    [key: string]: any;
  }

  interface DishOption {
    Id: number;
    StoreId?: number;
    Name: string;
    Type: number; // 0-单选，1-多选
    Items: DishOptionItem[];
    Description?: string;
  }

  interface DishItem {
    Id: number;
    StoreId?: number;
    LibraryItemId?: number;
    DishId?: number;
    Name: string;
    CategoryIds: number[];
    Description: string;
    Price: number;
    DefaultPrice?: number;
    ImageUrl: string;
    Options: number[];
    Tags: string[];
    Status: 0 | 1;
    Sort?: number;
    CreatedAt?: string;
    UpdatedAt?: string;
  }

  interface DishLibraryItem {
    Id: number;
    Name: string;
    Description: string;
    DefaultPrice: number;
    ImageUrl: string;
    CategoryIds: number[];
    Options: number[];
    Tags: string[];
    CreatedAt?: string;
    UpdatedAt?: string;
  }

  interface DishLibraryListData {
    Total: number;
    CurrentPage: number;
    PageSize: number;
    Items: DishLibraryItem[];
    Categories?: DishCategory[];
    Options?: DishOption[];
  }

  interface DishListData {
    Total: number;
    CurrentPage: number;
    PageSize: number;
    Items: DishItem[];
    Categories: DishCategory[];
    Options: DishOption[];
  }

  interface QueryDishesParams {
    current?: number;
    pageSize?: number;
    Keyword?: string;
  }

  interface UpdateDishStatusParams {
    Status: 0 | 1;
  }

  interface SaveDishStoreItemParams {
    LibraryItemId: number;
    Price: number;
    Status?: 0 | 1;
    Sort?: number;
  }

  interface UpdateDishStoreItemParams {
    Price: number;
    Status: 0 | 1;
    Sort?: number;
  }

  // 数据仪表盘
  interface StatsOverviewParams {
    StartDate?: string;
    EndDate?: string;
    Granularity?: 'day' | 'week' | 'month';
  }

  type CateringOverviewParams = StatsOverviewParams;

  interface StatsBaseOverview {
    StartDate: string;
    EndDate: string;
    Granularity: 'day' | 'week' | 'month';
    StoreId?: number;
  }

  interface StatTrendPoint {
    Date: string;
    [key: string]: string | number;
  }

  interface CateringSummary {
    Revenue: number;
    OrderCount: number;
    AvgOrderValue: number;
    CupCount: number;
  }

  interface CateringTrendPoint {
    Date: string;
    Revenue: number;
    OrderCount: number;
    CupCount: number;
  }

  interface CateringDishRankItem {
    DishName: string;
    Count: number;
    Revenue: number;
  }

  interface CateringHourlyPoint {
    Hour: number;
    OrderCount: number;
    CupCount: number;
  }

  interface CateringCategoryItem {
    CategoryName: string;
    Count: number;
    Revenue: number;
  }

  interface CateringPaymentItem {
    PayType: number | null;
    PayTypeText: string;
    OrderCount: number;
    Revenue: number;
  }

  interface CateringOverview {
    StartDate: string;
    EndDate: string;
    Granularity: 'day' | 'week' | 'month';
    StoreId?: number;
    Summary: CateringSummary;
    Trend: CateringTrendPoint[];
    DishRanking: CateringDishRankItem[];
    Hourly: CateringHourlyPoint[];
    Category: CateringCategoryItem[];
    Payment: CateringPaymentItem[];
  }

  interface OpsOverview {
    StartDate: string;
    EndDate: string;
    Granularity: 'day' | 'week' | 'month';
    StoreId?: number;
    Summary: {
      TotalRevenue: number;
      PlayRevenue: number;
      CateringRevenue: number;
      OrderCount: number;
      AvgOrderValue: number;
      NewUsers: number;
      ActiveUsers: number;
      RefundAmount: number;
      WalletRechargeAmount: number;
      PointEarned: number;
      PointConsumed: number;
    };
    Trend: Array<{
      Date: string;
      Revenue: number;
      PlayRevenue: number;
      CateringRevenue: number;
      OrderCount: number;
      NewUsers: number;
    }>;
  }

  interface PlayOverview {
    StartDate: string;
    EndDate: string;
    Granularity: 'day' | 'week' | 'month';
    StoreId?: number;
    Summary: {
      Revenue: number;
      OrderCount: number;
      AvgOrderValue: number;
      TotalPlayHours: number;
      AvgPlayHours: number;
      UniqueUsers: number;
    };
    Trend: Array<{
      Date: string;
      Revenue: number;
      OrderCount: number;
      TotalPlayHours: number;
    }>;
    BillingMode: Array<{
      BillingMode: number;
      BillingModeText: string;
      OrderCount: number;
      Revenue: number;
    }>;
    Payment: CateringPaymentItem[];
  }

  interface UserOverview {
    StartDate: string;
    EndDate: string;
    Granularity: 'day' | 'week' | 'month';
    StoreId?: number;
    Summary: {
      NewUsers: number;
      PaidUsers: number;
      NewPaidUsers: number;
      ReturningPaidUsers: number;
      NewUserPayRate: number;
      ActiveUsers: number;
    };
    Trend: Array<{
      Date: string;
      NewUsers: number;
    }>;
    SourceStore: Array<{
      StoreId?: number | null;
      StoreName: string;
      UserCount: number;
    }>;
  }

  interface CouponOverview {
    StartDate: string;
    EndDate: string;
    Granularity: 'day' | 'week' | 'month';
    StoreId?: number;
    Summary: {
      ReceivedCount: number;
      UsedCount: number;
      UseRate: number;
      OrderCount: number;
      Revenue: number;
      DiscountAmount: number;
    };
    Promotions: Array<{
      PromotionId: number;
      ActivityName: string;
      Title: string;
      CouponType?: number | null;
      CouponTypeText: string;
      IsReferralCoupon: boolean;
      ReceivedCount: number;
      UsedCount: number;
      UseRate: number;
      OrderCount: number;
      Revenue: number;
      DiscountAmount: number;
    }>;
    StoreDistribution: Array<{
      StoreId?: number | null;
      StoreName: string;
      UsedCount: number;
    }>;
  }

  interface ReferralOverview {
    StartDate: string;
    EndDate: string;
    Granularity: 'day' | 'week' | 'month';
    Summary: {
      BoundCount: number;
      NewUserCouponIssuedCount: number;
      FirstOrderCount: number;
      InviterRewardedCount: number;
      InviterCount: number;
      FirstOrderRate: number;
      RewardRate: number;
    };
    Trend: Array<{
      Date: string;
      BoundCount: number;
      NewUserCouponIssuedCount: number;
      FirstOrderCount: number;
      InviterRewardedCount: number;
    }>;
    ShareRanking: Array<{
      ShareId: string;
      BoundCount: number;
      FirstOrderCount: number;
      FirstOrderRate: number;
    }>;
  }

  interface MembershipOverview {
    StartDate: string;
    EndDate: string;
    Granularity: 'day' | 'week' | 'month';
    StoreId?: number;
    Summary: {
      Revenue: number;
      OpenCount: number;
      OpenUsers: number;
      ActiveMonthCardUsers: number;
      SubsidyAmount: number;
      PlayOrderCount: number;
      TotalPlayHours: number;
      CateringOrderCount: number;
      CateringRevenue: number;
    };
    Trend: Array<{
      Date: string;
      Revenue: number;
      OpenCount: number;
    }>;
    SourceDistribution: Array<{
      Source: MonthCardSource;
      SourceText: string;
      Revenue: number;
      OpenCount: number;
      OpenUsers: number;
      GiftedCount: number;
    }>;
  }

  interface WalletOverview {
    StartDate: string;
    EndDate: string;
    Granularity: 'day' | 'week' | 'month';
    StoreId?: number;
    Summary: {
      RechargeAmount: number;
      BonusAmount: number;
      RechargeCount: number;
      RechargeUsers: number;
      ConsumeAmount: number;
      BalanceTotal: number;
    };
    Trend: Array<{
      Date: string;
      RechargeAmount: number;
      BonusAmount: number;
      RechargeCount: number;
    }>;
    TierDistribution: Array<{
      Amount: number;
      BonusAmount: number;
      Label: string;
      RechargeCount: number;
    }>;
  }

  interface PointOverview {
    StartDate: string;
    EndDate: string;
    Granularity: 'day' | 'week' | 'month';
    StoreId?: number;
    Summary: {
      EarnedPoints: number;
      ConsumedPoints: number;
      BalanceTotal: number;
      RedeemOrderCount: number;
      RedeemPoints: number;
      WithdrawIssuedPoints: number;
    };
    Trend: Array<{
      Date: string;
      EarnedPoints: number;
      ConsumedPoints: number;
    }>;
    RedeemRanking: Array<{
      ProductName: string;
      Quantity: number;
      TotalPoints: number;
    }>;
  }

  interface UserInsightItem {
    OpenId: string;
    NickName?: string;
    RegisteredStoreId?: number | null;
    CreatedAt?: string | null;
    IsMonthCardUser: boolean;
    MonthCardExpire?: string | null;
    PlayOrderCount: number;
    CateringOrderCount: number;
    TotalOrderCount: number;
    PlayRevenue: number;
    CateringRevenue: number;
    TotalRevenue: number;
    TotalPlayHours: number;
    AvgOrderValue: number;
    CouponUsedCount: number;
    WalletRechargeAmount: number;
    PointBalance: number;
    LastOrderAt?: string | null;
    Tags: string[];
  }

  interface UserInsights {
    StartDate: string;
    EndDate: string;
    Granularity: 'day' | 'week' | 'month';
    StoreId?: number;
    Items: UserInsightItem[];
    Total: number;
  }

  // 充值档位
  interface WalletTierItem {
    Id: number;
    Amount: number;
    BonusAmount: number;
    Label: string;
    Sort: number;
    Enabled: 0 | 1;
    CreatedAt?: string;
    UpdatedAt?: string;
  }

  interface WalletTierListData {
    Total: number;
    CurrentPage: number;
    PageSize: number;
    Items: WalletTierItem[];
  }

  interface QueryWalletTiersParams {
    current?: number;
    pageSize?: number;
  }

  interface SaveWalletTierParams {
    Amount: number;
    BonusAmount: number;
    Label?: string;
    Sort: number;
    Enabled: 0 | 1;
  }

  interface UpdateWalletTierStatusParams {
    Enabled: 0 | 1;
  }

  // 积分商品分类
  interface PointCategoryItem {
    Id: number;
    Name: string;
    Sort: number;
    Status: 0 | 1;
    CreatedAt?: string;
    UpdatedAt?: string;
  }

  interface PointCategoryListData {
    Items: PointCategoryItem[];
    Total: number;
  }

  interface SavePointCategoryParams {
    Name: string;
    Sort: number;
    Status: 0 | 1;
  }

  // 积分商品
  interface PointProductItem {
    Id: number;
    Name: string;
    CategoryId?: number | null;
    CategoryName?: string;
    Description: string;
    PointsPrice: number;
    OriginalPrice?: number | null;
    SettlementPrice?: number | null;
    ImageUrl: string;
    Stock: number;
    Sort: number;
    Status: 0 | 1;
    RedeemStartAt?: string | null;
    MaxRedeemPerUser: number;
    CreatedAt?: string;
    UpdatedAt?: string;
  }

  interface PointProductListData {
    Total: number;
    CurrentPage: number;
    PageSize: number;
    Items: PointProductItem[];
    Categories: PointCategoryItem[];
  }

  interface QueryPointProductsParams {
    current?: number;
    pageSize?: number;
    Keyword?: string;
    CategoryId?: number;
  }

  interface UpdatePointStatusParams {
    Status: 0 | 1;
  }

  // 积分提取审计
  interface PointWithdrawItem {
    Id: number;
    OpenID: string;
    UserNickName: string;
    Points: number;
    Status: 0 | 1 | 2 | 3;
    StatusText: string;
    IssuerOpenID: string;
    IssuerNickName: string;
    IssuedAt?: string;
    ExpireAt?: string;
    CreatedAt?: string;
  }

  interface PointWithdrawListData {
    Total: number;
    CurrentPage: number;
    PageSize: number;
    Items: PointWithdrawItem[];
  }

  interface QueryPointWithdrawsParams {
    current?: number;
    pageSize?: number;
    Keyword?: string;
    Status?: 0 | 1 | 2 | 3;
  }

  // 积分兑换明细
  interface PointRedeemOrderItem {
    Id: number;
    OrderNo: string;
    OpenID: string;
    UserNickName: string;
    ProductId: number;
    ProductName: string;
    ProductImageUrl: string;
    PointsPrice: number;
    Quantity: number;
    TotalPoints: number;
    Status: 0 | 1 | 2;
    StatusText: string;
    VerifierOpenID: string;
    VerifierNickName: string;
    VerifiedAt?: string;
    CreatedAt?: string;
    UpdatedAt?: string;
  }

  interface PointRedeemOrderListData {
    Total: number;
    CurrentPage: number;
    PageSize: number;
    Items: PointRedeemOrderItem[];
  }

  interface QueryPointRedeemOrdersParams {
    current?: number;
    pageSize?: number;
    Keyword?: string;
    Status?: 0 | 1 | 2;
  }

  // 积分规则配置
  interface PointConfig {
    EarnThresholdAmount: number;
    EarnPoints: number;
    MaxWithdrawPerTime: number;
  }
}
