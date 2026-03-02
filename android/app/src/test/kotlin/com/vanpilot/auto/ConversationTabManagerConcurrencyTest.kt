package com.vanpilot.auto

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import java.util.concurrent.CountDownLatch
import java.util.concurrent.CyclicBarrier
import java.util.concurrent.Executors

/**
 * Concurrency tests for ConversationTabManager.
 *
 * Verifies that synchronized access prevents data corruption when
 * gRPC background threads and the UI thread access the manager
 * concurrently.
 */
@RunWith(JUnit4::class)
class ConversationTabManagerConcurrencyTest {

    companion object {
        private const val THREAD_COUNT = 8
        private const val MESSAGES_PER_THREAD = 200
    }

    @Test
    fun concurrentAddLeadAgentMessages_allMessagesStored() {
        val manager = ConversationTabManager()
        val barrier = CyclicBarrier(THREAD_COUNT)
        val latch = CountDownLatch(THREAD_COUNT)
        val executor = Executors.newFixedThreadPool(THREAD_COUNT)

        for (t in 0 until THREAD_COUNT) {
            executor.submit {
                barrier.await()
                for (i in 0 until MESSAGES_PER_THREAD) {
                    manager.addLeadAgentMessage(
                        ConversationMessage("thread-$t", "msg-$i", System.currentTimeMillis())
                    )
                }
                latch.countDown()
            }
        }

        latch.await()
        executor.shutdown()

        assertThat(manager.getLeadAgentMessages()).hasSize(THREAD_COUNT * MESSAGES_PER_THREAD)
    }

    @Test
    fun concurrentAddSubAgentMessages_allMessagesStored() {
        val manager = ConversationTabManager()
        manager.addSubAgent("agent1")
        val barrier = CyclicBarrier(THREAD_COUNT)
        val latch = CountDownLatch(THREAD_COUNT)
        val executor = Executors.newFixedThreadPool(THREAD_COUNT)

        for (t in 0 until THREAD_COUNT) {
            executor.submit {
                barrier.await()
                for (i in 0 until MESSAGES_PER_THREAD) {
                    manager.addSubAgentMessage(
                        "agent1",
                        ConversationMessage("thread-$t", "msg-$i", System.currentTimeMillis())
                    )
                }
                latch.countDown()
            }
        }

        latch.await()
        executor.shutdown()

        assertThat(manager.getSubAgentMessages("agent1"))
            .hasSize(THREAD_COUNT * MESSAGES_PER_THREAD)
    }

    @Test
    fun concurrentReadAndWrite_noException() {
        val manager = ConversationTabManager()
        manager.addSubAgent("reader-test")
        val barrier = CyclicBarrier(THREAD_COUNT)
        val latch = CountDownLatch(THREAD_COUNT)
        val executor = Executors.newFixedThreadPool(THREAD_COUNT)
        val errors = mutableListOf<Throwable>()

        // Half the threads write, half read
        for (t in 0 until THREAD_COUNT) {
            executor.submit {
                try {
                    barrier.await()
                    for (i in 0 until MESSAGES_PER_THREAD) {
                        if (t % 2 == 0) {
                            manager.addLeadAgentMessage(
                                ConversationMessage("writer-$t", "msg-$i", System.currentTimeMillis())
                            )
                            manager.addSubAgentMessage(
                                "reader-test",
                                ConversationMessage("writer-$t", "msg-$i", System.currentTimeMillis())
                            )
                        } else {
                            manager.getLeadAgentMessages()
                            manager.getSubAgentMessages("reader-test")
                            manager.getSubAgentIds()
                            manager.getAllConversationTabIds()
                        }
                    }
                } catch (e: Throwable) {
                    synchronized(errors) { errors.add(e) }
                } finally {
                    latch.countDown()
                }
            }
        }

        latch.await()
        executor.shutdown()

        assertThat(errors).isEmpty()
    }

    @Test
    fun concurrentActiveTabIdReadWrite_noException() {
        val manager = ConversationTabManager()
        val barrier = CyclicBarrier(THREAD_COUNT)
        val latch = CountDownLatch(THREAD_COUNT)
        val executor = Executors.newFixedThreadPool(THREAD_COUNT)
        val errors = mutableListOf<Throwable>()

        for (t in 0 until THREAD_COUNT) {
            executor.submit {
                try {
                    barrier.await()
                    for (i in 0 until MESSAGES_PER_THREAD) {
                        if (t % 2 == 0) {
                            manager.activeConversationTabId = "tab-$t-$i"
                        } else {
                            manager.activeConversationTabId // read
                        }
                    }
                } catch (e: Throwable) {
                    synchronized(errors) { errors.add(e) }
                } finally {
                    latch.countDown()
                }
            }
        }

        latch.await()
        executor.shutdown()

        assertThat(errors).isEmpty()
    }

    @Test
    fun concurrentAddAndRemoveSubAgents_noException() {
        val manager = ConversationTabManager()
        val barrier = CyclicBarrier(THREAD_COUNT)
        val latch = CountDownLatch(THREAD_COUNT)
        val executor = Executors.newFixedThreadPool(THREAD_COUNT)
        val errors = mutableListOf<Throwable>()

        for (t in 0 until THREAD_COUNT) {
            executor.submit {
                try {
                    barrier.await()
                    for (i in 0 until MESSAGES_PER_THREAD) {
                        val agentId = "agent-${i % 3}"
                        manager.addSubAgent(agentId)
                        manager.getSubAgentIds()
                        manager.removeSubAgent(agentId)
                    }
                } catch (e: Throwable) {
                    synchronized(errors) { errors.add(e) }
                } finally {
                    latch.countDown()
                }
            }
        }

        latch.await()
        executor.shutdown()

        assertThat(errors).isEmpty()
    }
}
