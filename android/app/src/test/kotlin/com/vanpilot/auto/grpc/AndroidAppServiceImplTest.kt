package com.vanpilot.auto.grpc

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.ByteString
import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.proto.v1.AndroidAppServiceGrpc
import com.vanpilot.proto.v1.GetCurrentDisplayRequest
import com.vanpilot.proto.v1.QueryCacheRequest
import com.vanpilot.proto.v1.RequestScreenshotRequest
import io.grpc.ManagedChannel
import io.grpc.inprocess.InProcessChannelBuilder
import io.grpc.inprocess.InProcessServerBuilder
import io.grpc.Server
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class AndroidAppServiceImplTest {

    private lateinit var serverName: String
    private lateinit var server: Server
    private lateinit var channel: ManagedChannel
    private lateinit var stub: AndroidAppServiceGrpc.AndroidAppServiceBlockingStub
    private lateinit var cache: BitmapCache

    private var currentDisplayKey: String? = null
    private var screenshotData: ByteArray? = null

    @Before
    fun setUp() {
        cache = BitmapCache(maxSize = 16)
        currentDisplayKey = null
        screenshotData = null

        val service = AndroidAppServiceImpl(
            cache = cache,
            getCurrentDisplayKey = { currentDisplayKey },
            captureScreenshot = { screenshotData }
        )

        serverName = InProcessServerBuilder.generateName()
        server = InProcessServerBuilder.forName(serverName)
            .directExecutor()
            .addService(service)
            .build()
            .start()
        channel = InProcessChannelBuilder.forName(serverName)
            .directExecutor()
            .build()
        stub = AndroidAppServiceGrpc.newBlockingStub(channel)
    }

    @After
    fun tearDown() {
        channel.shutdownNow()
        server.shutdownNow()
    }

    @Test
    fun getCurrentDisplay_noDisplay_returnsEmptyKey() {
        currentDisplayKey = null

        val response = stub.getCurrentDisplay(GetCurrentDisplayRequest.getDefaultInstance())

        assertThat(response.currentCacheKey).isEmpty()
    }

    @Test
    fun getCurrentDisplay_withDisplay_returnsCacheKey() {
        currentDisplayKey = "0xDEAD"

        val response = stub.getCurrentDisplay(GetCurrentDisplayRequest.getDefaultInstance())

        assertThat(response.currentCacheKey).isEqualTo("0xDEAD")
    }

    @Test
    fun requestScreenshot_noScreenshot_returnsEmptyBytes() {
        screenshotData = null

        val response = stub.requestScreenshot(RequestScreenshotRequest.getDefaultInstance())

        assertThat(response.screenshot).isEqualTo(ByteString.EMPTY)
    }

    @Test
    fun requestScreenshot_withScreenshot_returnsPngData() {
        val pngData = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A)
        screenshotData = pngData

        val response = stub.requestScreenshot(RequestScreenshotRequest.getDefaultInstance())

        assertThat(response.screenshot.toByteArray()).isEqualTo(pngData)
    }

    @Test
    fun queryCache_emptyRequest_returnsAllKeys() {
        cache.put("a", byteArrayOf(1))
        cache.put("b", byteArrayOf(2))
        cache.put("c", byteArrayOf(3))

        val response = stub.queryCache(QueryCacheRequest.getDefaultInstance())

        assertThat(response.presentKeysList).containsExactly("a", "b", "c")
        assertThat(response.missingKeysList).isEmpty()
    }

    @Test
    fun queryCache_specificKeys_partitionsCorrectly() {
        cache.put("a", byteArrayOf(1))
        cache.put("c", byteArrayOf(3))

        val request = QueryCacheRequest.newBuilder()
            .addKeys("a")
            .addKeys("b")
            .addKeys("c")
            .build()

        val response = stub.queryCache(request)

        assertThat(response.presentKeysList).containsExactly("a", "c")
        assertThat(response.missingKeysList).containsExactly("b")
    }

    @Test
    fun queryCache_allMissing_returnsAllAsMissing() {
        val request = QueryCacheRequest.newBuilder()
            .addKeys("x")
            .addKeys("y")
            .build()

        val response = stub.queryCache(request)

        assertThat(response.presentKeysList).isEmpty()
        assertThat(response.missingKeysList).containsExactly("x", "y")
    }

    @Test
    fun queryCache_emptyCache_emptyRequest_returnsNothing() {
        val response = stub.queryCache(QueryCacheRequest.getDefaultInstance())

        assertThat(response.presentKeysList).isEmpty()
        assertThat(response.missingKeysList).isEmpty()
    }
}
