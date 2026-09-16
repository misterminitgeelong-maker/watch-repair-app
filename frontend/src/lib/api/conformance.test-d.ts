/**
 * Type-level conformance between the hand-written API types and the backend.
 *
 * `src/lib/api/index.ts` hand-writes ~197 interfaces that mirror the backend's
 * response schemas. `src/lib/generated/openapi.d.ts` is generated from the
 * backend's own OpenAPI document. Until now the two were never compared, and
 * they had diverged: when this file was written, the checked-in OpenAPI
 * document was missing 121 of 297 endpoints, and of the 40 types that could be
 * paired by name, 16 disagreed with the backend.
 *
 * The disagreements were not cosmetic. Two kinds mattered:
 *
 *   1. The backend can return `null` for a field the hand-written type declared
 *      as `string | undefined`. Code that checks `x !== undefined` then treats a
 *      null as a present value.
 *   2. The hand-written type was *narrower* than the backend — declaring
 *      `status: "new" | "processed" | "dismissed"` where the backend returns a
 *      plain string. This is the dangerous direction: a new status added
 *      server-side flows into an exhaustive switch that TypeScript believes is
 *      already total, so nothing warns.
 *
 * Each assertion below says: a value of the backend's shape is assignable to the
 * hand-written type. That is the direction that matters — we receive these from
 * the server, so the hand-written type must accept everything the server can
 * send. The reverse (hand-written assignable to generated) is deliberately not
 * asserted: a hand-written type is allowed to be a permissive superset.
 *
 * This file is type-checked, never executed. `npm run typecheck` fails the build
 * when the backend changes shape and the hand-written type is not updated.
 *
 * Adding a pair: name the hand-written interface exactly as the backend names
 * its schema and add a line here. The 157 unpaired interfaces are named
 * differently from their backend counterparts; aligning them is incremental
 * work, and every one that gets aligned can be added below.
 */
import type { components } from '../generated/openapi'
import type * as Api from './index'

type Schema<K extends keyof components['schemas']> = components['schemas'][K]

/** Asserts the backend's shape is assignable to the hand-written type. */
type AcceptsBackend<HandWritten, Generated extends HandWritten> = Generated

/**
 * Known divergence, deliberately not asserted:
 *
 * `CustomerPortalLookupResponse` — its nested `pending_actions` is declared by the
 * backend as a bare `{ additionalProperties: true }` object, so the generated type
 * carries no field information at all. Asserting against it would mean deleting the
 * frontend's `CustomerPortalPendingAction` type and replacing a useful shape with
 * `object`. The fix belongs on the backend: give that field a real response model.
 * Until then the frontend type is the better of the two and stays as it is.
 */
export type Conformance = [
  AcceptsBackend<Api.ActiveSiteSwitchResponse, Schema<'ActiveSiteSwitchResponse'>>,
  AcceptsBackend<Api.AutoKeyJobStatusUpdateResult, Schema<'AutoKeyJobStatusUpdateResult'>>,
  AcceptsBackend<Api.BillingLimitsResponse, Schema<'BillingLimitsResponse'>>,
  AcceptsBackend<Api.BillingLimitsUsage, Schema<'BillingLimitsUsage'>>,
  AcceptsBackend<Api.BillingPlanLimits, Schema<'BillingPlanLimits'>>,
  AcceptsBackend<Api.CustomerAccountCreate, Schema<'CustomerAccountCreate'>>,
  AcceptsBackend<Api.CustomerAccountStatementLine, Schema<'CustomerAccountStatementLine'>>,
  AcceptsBackend<Api.CustomerLoyaltyRead, Schema<'CustomerLoyaltyRead'>>,
  AcceptsBackend<Api.CustomerOrderImportResult, Schema<'CustomerOrderImportResult'>>,
  AcceptsBackend<Api.GarageServicingPricingRow, Schema<'GarageServicingPricingRow'>>,
  AcceptsBackend<Api.InboundEmailDetail, Schema<'InboundEmailDetail'>>,
  AcceptsBackend<Api.InboundEmailJobCreateRequest, Schema<'InboundEmailJobCreateRequest'>>,
  AcceptsBackend<Api.InboundEmailJobCreateResult, Schema<'InboundEmailJobCreateResult'>>,
  AcceptsBackend<Api.InboundEmailListItem, Schema<'InboundEmailListItem'>>,
  AcceptsBackend<Api.JobThreadMessage, Schema<'JobThreadMessage'>>,
  AcceptsBackend<Api.LatLng, Schema<'LatLng'>>,
  AcceptsBackend<Api.LoyaltyProfileResponse, Schema<'LoyaltyProfileResponse'>>,
  AcceptsBackend<Api.MinitHqEnterShopResponse, Schema<'MinitHqEnterShopResponse'>>,
  AcceptsBackend<Api.MobileSuburbRouteOperatorSummary, Schema<'MobileSuburbRouteOperatorSummary'>>,
  AcceptsBackend<Api.MobileSuburbRoutesSummary, Schema<'MobileSuburbRoutesSummary'>>,
  AcceptsBackend<Api.MultiSiteLoginResponse, Schema<'MultiSiteLoginResponse'>>,
  AcceptsBackend<Api.OemKeyPricingRow, Schema<'OemKeyPricingRow'>>,
  AcceptsBackend<Api.OptimizeDrivingRouteResponse, Schema<'OptimizeDrivingRouteResponse'>>,
  AcceptsBackend<Api.ParentDashboardBookingSnippet, Schema<'ParentDashboardBookingSnippet'>>,
  AcceptsBackend<Api.ParentEmailLeadsByShopReport, Schema<'ParentEmailLeadsByShopReport'>>,
  AcceptsBackend<Api.ParentMobileJobsReport, Schema<'ParentMobileJobsReport'>>,
  AcceptsBackend<Api.ParentOperationsOverview, Schema<'ParentOperationsOverview'>>,
  AcceptsBackend<Api.ParentRegionDashboardStat, Schema<'ParentRegionDashboardStat'>>,
  AcceptsBackend<Api.ParentShopBookingVolume, Schema<'ParentShopBookingVolume'>>,
  AcceptsBackend<Api.ParentShopBookingsReport, Schema<'ParentShopBookingsReport'>>,
  AcceptsBackend<Api.ParentTroubleshootingItem, Schema<'ParentTroubleshootingItem'>>,
  AcceptsBackend<Api.PlatformEnterShopResponse, Schema<'PlatformEnterShopResponse'>>,
  AcceptsBackend<Api.Prospect, Schema<'Prospect'>>,
  AcceptsBackend<Api.ProspectSearchResponse, Schema<'ProspectSearchResponse'>>,
  AcceptsBackend<Api.ServicePricingRow, Schema<'ServicePricingRow'>>,
  AcceptsBackend<Api.ShopEmailLeadBucket, Schema<'ShopEmailLeadBucket'>>,
  AcceptsBackend<Api.ShopMobileBookingCreate, Schema<'ShopMobileBookingCreate'>>,
  AcceptsBackend<Api.ShopMobileOperatorOption, Schema<'ShopMobileOperatorOption'>>,
  AcceptsBackend<Api.StockImportSummaryResponse, Schema<'StockImportSummaryResponse'>>,
  AcceptsBackend<Api.VswtCommitFile, Schema<'VswtCommitFile'>>,
]
