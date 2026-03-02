package com.vanpilot.auto

import com.google.common.truth.Truth.assertThat
import com.google.common.truth.Truth.assertWithMessage
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.CyclicBarrier
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Concurrent access tests for ConversationTabManager.
 *
 * ConversationTabManager uses plain ArrayList and HashMap without synchronization.
 * This is currently safe because the Car App Library guarantees that
 * onGetTemplate() calls (which read messages) are single-threaded.
 *
 * These tests:
 * 1. Document the single-threaded assumption explicitly
 * 2. Demonstrate that concurrent access IS unsafe (stress tests)
 *
 * When gRPC message callbacks are wired to the tab manager from a different
 * thread (future integration), synchronization must be added. At that point,
 * update the stress tests to verify thread-safety instead of unsafety.
 *
 * See: GitHub issue #35
 */
@RunWith(JUnit4::class)
class ConversationTabManagerConcurrentTest {

    private lateinit var manager: ConversationTabManager

    @Before
    fun setUp() {
        manager = ConversationTabManager()
    }

    // =========================================================================
    // Single-threaded assumption documentation
    // =========================================================================

    /**
     * Documents the single-threaded access contract.
     *
     * Car App Library guarantees that onGetTemplate() is called on the main
     * thread. As long as addLeadAgentMessage() / addSubAgentMessage() are also
     * called on the main thread, no synchronization is needed.
     *
     * This test verifies correctness under the assumed single-threaded model:
     * interleaved reads and writes from one thread always produce consistent state.
     */
    @Test
    fun singleThreadedAccess_interleavedReadsAndWrites_isConsistent() {
        for (i in 1..100) {
            manager.addLeadAgentMessage(ConversationMessage("lead", "msg$i", i.toLong()))
            val messages = manager.getLeadAgentMessages()
            assertThat(messages).hasSize(i)
            assertThat(messages.last().text).isEqualTo("msg$i")
        }
    }

    /**
     * Documents that sub-agent operations are also safe under single-threaded access.
     * Interleaved addSubAgent / addSubAgentMessage / getSubAgentMessages calls
     * from one thread are always consistent.
     */
    @Test
    fun singleThreadedAccess_subAgentInterleavedOps_isConsistent() {
        manager.addSubAgent("researcher")
        for (i in 1..50) {
            manager.addSubAgentMessage(
                "researcher",
                ConversationMessage("researcher", "msg$i", i.toLong())
            )
            val messages = manager.getSubAgentMessages("researcher")
            assertThat(messages).hasSize(i)
            assertThat(messages.last().text).isEqualTo("msg$i")
        }
    }

    // =========================================================================
    // Concurrent stress tests
    // =========================================================================

    /**
     * Stress test: concurrent writes to leadAgentMessages from multiple threads.
     *
     * ArrayList.add() is not atomic — two threads can read the same `size`,
     * both write to the same slot, and only increment size once. With 8
     * threads x 1000 messages = 8000 total adds, data loss from racy
     * writes is virtually certain.
     *
     * When synchronization is added to ConversationTabManager, update this
     * test to assert that all writes are preserved:
     *   assertThat(actualMessages.size).isEqualTo(expectedTotal)
     *   assertThat(raceDetected).isFalse()
     */
    @Test
    fun concurrentWrites_leadAgent_detectsUnsafety() {
        val writerCount = 8
        val messagesPerWriter = 1000
        val barrier = CyclicBarrier(writerCount)
        val errors = ConcurrentLinkedQueue<Throwable>()

        val writers = (1..writerCount).map { threadId ->
            Thread {
                try {
                    barrier.await()
                    for (i in 1..messagesPerWriter) {
                        manager.addLeadAgentMessage(
                            ConversationMessage("t$threadId", "msg$i", i.toLong())
                        )
                    }
                } catch (e: Throwable) {
                    errors.add(e)
                }
            }
        }

        writers.forEach { it.start() }
        writers.forEach { it.join(10_000) }

        val expectedTotal = writerCount * messagesPerWriter
        val actualMessages = try {
            manager.getLeadAgentMessages()
        } catch (e: Throwable) {
            errors.add(e)
            emptyList()
        }

        val hasRaceEvidence = errors.isNotEmpty()
            || actualMessages.size != expectedTotal
            || actualMessages.any { it == null }

        // This assertion documents that the class IS NOT thread-safe.
        // When synchronization is added, change to:
        //   assertWithMessage(...).that(hasRaceEvidence).isFalse()
        assertWithMessage(
            "Expected race condition evidence: " +
                "errors=${errors.size}, " +
                "expected=$expectedTotal, " +
                "actual=${actualMessages.size}"
        ).that(hasRaceEvidence).isTrue()
    }

    /**
     * Stress test: concurrent reads during writes on lead agent messages.
     *
     * getLeadAgentMessages() calls toList() which iterates the backing
     * ArrayList. Concurrent modification during iteration can throw
     * ConcurrentModificationException or produce inconsistent snapshots.
     *
     * When synchronization is added, update this test to assert:
     *   assertThat(raceDetected.get()).isFalse()
     *   assertThat(actualSize).isEqualTo(expectedTotal)
     */
    @Test
    fun concurrentReadsAndWrites_leadAgent_detectsUnsafety() {
        val writerCount = 4
        val readerCount = 4
        val iterations = 1000
        val barrier = CyclicBarrier(writerCount + readerCount)
        val errors = ConcurrentLinkedQueue<Throwable>()
        val raceDetected = AtomicBoolean(false)

        val writers = (1..writerCount).map { threadId ->
            Thread {
                try {
                    barrier.await()
                    for (i in 1..iterations) {
                        manager.addLeadAgentMessage(
                            ConversationMessage("t$threadId", "msg$i", i.toLong())
                        )
                    }
                } catch (e: Throwable) {
                    errors.add(e)
                    raceDetected.set(true)
                }
            }
        }

        val readers = (1..readerCount).map {
            Thread {
                try {
                    barrier.await()
                    for (i in 1..iterations) {
                        try {
                            manager.getLeadAgentMessages().size
                        } catch (e: ConcurrentModificationException) {
                            errors.add(e)
                            raceDetected.set(true)
                        } catch (e: ArrayIndexOutOfBoundsException) {
                            errors.add(e)
                            raceDetected.set(true)
                        }
                    }
                } catch (e: Throwable) {
                    errors.add(e)
                    raceDetected.set(true)
                }
            }
        }

        (writers + readers).forEach { it.start() }
        (writers + readers).forEach { it.join(10_000) }

        val expectedTotal = writerCount * iterations
        val actualSize = try {
            manager.getLeadAgentMessages().size
        } catch (e: Throwable) {
            errors.add(e)
            raceDetected.set(true)
            -1
        }

        val hasRaceEvidence = raceDetected.get() || actualSize != expectedTotal

        // This assertion documents that the class IS NOT thread-safe.
        // When synchronization is added, change to:
        //   assertWithMessage(...).that(hasRaceEvidence).isFalse()
        assertWithMessage(
            "Expected race condition evidence: " +
                "errors=${errors.size}, " +
                "expected=$expectedTotal, " +
                "actual=$actualSize"
        ).that(hasRaceEvidence).isTrue()
    }

    /**
     * Stress test: concurrent sub-agent message writes and reads.
     *
     * HashMap.get() and the backing MutableList.add() are both racy
     * under concurrent access. This test exercises the sub-agent code path
     * to demonstrate that it is also not thread-safe.
     *
     * When synchronization is added, update this test to assert:
     *   assertThat(raceDetected.get()).isFalse()
     *   assertThat(actualSize).isEqualTo(expectedTotal)
     */
    @Test
    fun concurrentSubAgentOps_detectsUnsafety() {
        manager.addSubAgent("shared")

        val writerCount = 4
        val readerCount = 2
        val iterations = 1000
        val barrier = CyclicBarrier(writerCount + readerCount)
        val errors = ConcurrentLinkedQueue<Throwable>()
        val raceDetected = AtomicBoolean(false)

        val messageWriters = (1..writerCount).map { threadId ->
            Thread {
                try {
                    barrier.await()
                    for (i in 1..iterations) {
                        try {
                            manager.addSubAgentMessage(
                                "shared",
                                ConversationMessage("t$threadId", "msg$i", i.toLong())
                            )
                        } catch (e: Throwable) {
                            errors.add(e)
                            raceDetected.set(true)
                        }
                    }
                } catch (e: Throwable) {
                    errors.add(e)
                    raceDetected.set(true)
                }
            }
        }

        val readers = (1..readerCount).map {
            Thread {
                try {
                    barrier.await()
                    for (i in 1..iterations) {
                        try {
                            manager.getSubAgentMessages("shared").size
                        } catch (e: ConcurrentModificationException) {
                            errors.add(e)
                            raceDetected.set(true)
                        } catch (e: ArrayIndexOutOfBoundsException) {
                            errors.add(e)
                            raceDetected.set(true)
                        }
                    }
                } catch (e: Throwable) {
                    errors.add(e)
                    raceDetected.set(true)
                }
            }
        }

        (messageWriters + readers).forEach { it.start() }
        (messageWriters + readers).forEach { it.join(10_000) }

        val expectedTotal = writerCount * iterations
        val actualSize = try {
            manager.getSubAgentMessages("shared").size
        } catch (e: Throwable) {
            errors.add(e)
            raceDetected.set(true)
            -1
        }

        val hasRaceEvidence = raceDetected.get() || actualSize != expectedTotal

        // This assertion documents that the class IS NOT thread-safe.
        // When synchronization is added, change to:
        //   assertWithMessage(...).that(raceDetected.get()).isFalse()
        //   assertThat(actualSize).isEqualTo(expectedTotal)
        assertWithMessage(
            "Expected race condition evidence for sub-agent ops: " +
                "errors=${errors.size}, " +
                "expected=$expectedTotal, " +
                "actual=$actualSize"
        ).that(hasRaceEvidence).isTrue()
    }
}
