package com.vanpilot.auto.grpc

import com.vanpilot.proto.v1.GetBitmapRequest
import com.vanpilot.proto.v1.GetBitmapResponse
import com.vanpilot.proto.v1.GetEventsRequest
import com.vanpilot.proto.v1.GetEventsResponse
import com.vanpilot.proto.v1.ReportThemeRequest
import com.vanpilot.proto.v1.ReportThemeResponse
import com.vanpilot.proto.v1.SendUserInputRequest
import com.vanpilot.proto.v1.SendUserInputResponse
import com.vanpilot.proto.v1.SyncServiceGrpc
import com.vanpilot.proto.v1.ThemeMode
import io.grpc.ManagedChannel

/**
 * Client wrapper for the SyncService gRPC service.
 *
 * The Android app uses this to pull events from the Mac Studio supervisor,
 * send transcribed voice input, and request bitmaps not in the local cache.
 */
class SyncServiceClient(private val channel: ManagedChannel) {

    private val stub: SyncServiceGrpc.SyncServiceBlockingStub =
        SyncServiceGrpc.newBlockingStub(channel)

    fun getEvents(sinceTimestampMs: Long, maxCount: Int): GetEventsResponse {
        val request = GetEventsRequest.newBuilder()
            .setSinceTimestampMs(sinceTimestampMs)
            .setMaxCount(maxCount)
            .build()
        return stub.getEvents(request)
    }

    fun sendUserInput(text: String, targetAgentId: String = "lead"): SendUserInputResponse {
        val request = SendUserInputRequest.newBuilder()
            .setText(text)
            .setTargetAgentId(targetAgentId)
            .build()
        return stub.sendUserInput(request)
    }

    fun getBitmap(cacheKey: String): GetBitmapResponse {
        val request = GetBitmapRequest.newBuilder()
            .setCacheKey(cacheKey)
            .build()
        return stub.getBitmap(request)
    }

    fun reportTheme(theme: ThemeMode): ReportThemeResponse {
        val request = ReportThemeRequest.newBuilder()
            .setTheme(theme)
            .build()
        return stub.reportTheme(request)
    }

    fun shutdown() {
        channel.shutdown()
    }
}
