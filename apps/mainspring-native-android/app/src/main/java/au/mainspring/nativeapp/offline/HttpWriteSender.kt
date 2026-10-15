package au.mainspring.nativeapp.offline

import au.mainspring.nativeapp.api.OfflineReplayApi
import com.google.gson.JsonParser
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Sends queued writes with replay safety:
 *  - every request carries `Idempotency-Key` (the backend records the outcome per key, so a retry after a timeout
 *    the server did receive returns the first result instead of posting a second note or status change);
 *  - mobile status changes carry `X-Expected-Updated-At` (the server answers 409 `stale_write` when the job has moved on);
 *  - watch/shoe status changes have no server-side stale check, so the live job is read first and the change is only
 *    sent while its status is still what the user saw. A different status is reported as 412 (stale).
 * Returns the HTTP status for [OfflineWriteQueue]; 200 may also mean "already applied, nothing to send".
 */
class HttpWriteSender(private val api: () -> OfflineReplayApi) : WriteSender {
    private val json = "application/json; charset=UTF-8".toMediaType()

    override suspend fun send(write: QueuedWrite): Int {
        val service = api()
        if (!write.force && write.baseStatus != null && write.targetStatus != null &&
            (write.kind == OfflineKinds.WATCH_STATUS || write.kind == OfflineKinds.SHOE_STATUS)
        ) {
            val resp = service.get(write.endpoint.removeSuffix("/status"))
            val text = try { resp.body()?.string() } finally { resp.errorBody()?.close() }
            if (!resp.isSuccessful) return resp.code()
            val live = try { JsonParser.parseString(text).asJsonObject.get("status")?.asString } catch (_: Exception) { null }
            // Unreadable job: fall through and let the server decide rather than blocking the queue.
            if (live != null) {
                if (live == write.targetStatus) return 200 // already applied (for example a send that timed out after the server got it)
                if (live != write.baseStatus) return 412
            }
        }
        val headers = buildMap {
            put("Idempotency-Key", write.effectiveIdempotencyKey())
            val expected = write.expectedUpdatedAt
            if (!write.force && write.kind == OfflineKinds.MOBILE_STATUS && !expected.isNullOrBlank()) put("X-Expected-Updated-At", expected)
        }
        val body = write.body.toRequestBody(json)
        val resp = when (write.method) {
            "POST" -> service.post(write.endpoint, body, headers)
            "PUT" -> service.put(write.endpoint, body, headers)
            "PATCH" -> service.patch(write.endpoint, body, headers)
            else -> return 400
        }
        val code = resp.code()
        val errorText = try { resp.errorBody()?.string() } catch (_: Exception) { null }
        resp.body()?.close()
        // The first attempt may still be running on the server: not a conflict, try again later.
        if (code == 409 && errorText?.contains("idempotent_request_in_progress") == true) return 503
        return code
    }
}
