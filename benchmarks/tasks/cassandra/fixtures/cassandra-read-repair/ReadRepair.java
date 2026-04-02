/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.apache.cassandra.service;

import java.util.concurrent.ThreadLocalRandom;

import org.apache.cassandra.config.DatabaseDescriptor;
import org.apache.cassandra.db.ConsistencyLevel;
import org.apache.cassandra.db.ReadResponse;
import org.apache.cassandra.exceptions.ReadTimeoutException;
import org.apache.cassandra.locator.InetAddressAndPort;
import org.apache.cassandra.metrics.ReadRepairMetrics;
import org.apache.cassandra.net.MessagingService;
import org.apache.cassandra.utils.FBUtilities;

/**
 * Coordinates background read repair for Apache Cassandra.
 *
 * Read repair is controlled by the {@code read_repair_chance} setting in
 * cassandra.yaml. When a read triggers repair, this class reconciles
 * divergent replicas and writes the most recent data back to stale nodes.
 *
 * The probability of performing read repair on any given read is determined
 * by read_repair_chance (global) and dc_local_read_repair_chance (cross-DC).
 */
public class ReadRepair
{
    /** Default value for read_repair_chance when not explicitly configured. */
    public static final double DEFAULT_READ_REPAIR_CHANCE = 0.1;

    /**
     * Evaluates whether a background read repair should run for this request.
     * Controlled by the read_repair_chance configuration parameter.
     *
     * @param consistency the consistency level of the read operation
     * @return true if read repair should be triggered based on read_repair_chance
     */
    public static boolean shouldPerformReadRepair(ConsistencyLevel consistency)
    {
        double chance = DatabaseDescriptor.getReadRepairChance();
        if (chance == 0.0)
            return false;
        return ThreadLocalRandom.current().nextDouble() < chance;
    }

    /**
     * Initiates a background repair for the given replica set.
     * Called when read_repair_chance triggers a repair for a read operation.
     *
     * @param endpoints the replica endpoints to repair
     * @param response the authoritative read response to propagate
     */
    public static void repairInBackground(InetAddressAndPort[] endpoints, ReadResponse response)
    {
        ReadRepairMetrics.attempted.inc();
        for (InetAddressAndPort endpoint : endpoints)
        {
            if (!endpoint.equals(FBUtilities.getBroadcastAddressAndPort()))
                MessagingService.instance().send(response.toRepairMessage(), endpoint);
        }
    }

    /**
     * Returns the effective read_repair_chance taking locality into account.
     * Uses dc_local_read_repair_chance for local-DC operations and
     * read_repair_chance for cross-DC operations.
     *
     * @param localDatacenter true if the operation is scoped to the local DC
     * @return the applicable read_repair_chance value
     */
    public static double effectiveReadRepairChance(boolean localDatacenter)
    {
        if (localDatacenter)
            return DatabaseDescriptor.getDcLocalReadRepairChance();
        return DatabaseDescriptor.getReadRepairChance();
    }

    /**
     * Validates that a proposed read_repair_chance value is in range.
     *
     * @param chance the proposed read_repair_chance
     * @throws IllegalArgumentException if the value is out of [0.0, 1.0]
     */
    public static void validateReadRepairChance(double chance)
    {
        if (chance < 0.0 || chance > 1.0)
            throw new IllegalArgumentException(
                "read_repair_chance must be between 0.0 and 1.0, got: " + chance);
    }
}
