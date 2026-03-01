package com.vanpilot.auto.grpc

import com.google.protobuf.ByteString
import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.proto.v1.AndroidAppServiceGrpc
import com.vanpilot.proto.v1.GetCurrentDisplayRequest
import com.vanpilot.proto.v1.GetCurrentDisplayResponse
import com.vanpilot.proto.v1.QueryCacheRequest
import com.vanpilot.proto.v1.QueryCacheResponse
import com.vanpilot.proto.v1.RequestScreenshotRequest
import com.vanpilot.proto.v1.RequestScreenshotResponse
import io.grpc.stub.StreamObserver

/**
 * Server-side implementation of AndroidAppService.
 *
 * Hosted by the Android app so the Mac Studio supervisor can query
 * the app's display state and bitmap cache.
 */
class AndroidAppServiceImpl(
    private val cache: BitmapCache,
    private val getCurrentDisplayKey: () -> String?,
    private val captureScreenshot: () -> ByteArray?
) : AndroidAppServiceGrpc.AndroidAppServiceImplBase() {

    override fun getCurrentDisplay(
        request: GetCurrentDisplayRequest,
        responseObserver: StreamObserver<GetCurrentDisplayResponse>
    ) {
        val key = getCurrentDisplayKey() ?: ""
        val response = GetCurrentDisplayResponse.newBuilder()
            .setCurrentCacheKey(key)
            .build()
        responseObserver.onNext(response)
        responseObserver.onCompleted()
    }

    override fun requestScreenshot(
        request: RequestScreenshotRequest,
        responseObserver: StreamObserver<RequestScreenshotResponse>
    ) {
        val screenshot = captureScreenshot() ?: ByteArray(0)
        val response = RequestScreenshotResponse.newBuilder()
            .setScreenshot(ByteString.copyFrom(screenshot))
            .build()
        responseObserver.onNext(response)
        responseObserver.onCompleted()
    }

    override fun queryCache(
        request: QueryCacheRequest,
        responseObserver: StreamObserver<QueryCacheResponse>
    ) {
        val requestedKeys = request.keysList
        val builder = QueryCacheResponse.newBuilder()

        if (requestedKeys.isEmpty()) {
            builder.addAllPresentKeys(cache.keys())
        } else {
            for (key in requestedKeys) {
                if (cache.contains(key)) {
                    builder.addPresentKeys(key)
                } else {
                    builder.addMissingKeys(key)
                }
            }
        }

        responseObserver.onNext(builder.build())
        responseObserver.onCompleted()
    }
}
