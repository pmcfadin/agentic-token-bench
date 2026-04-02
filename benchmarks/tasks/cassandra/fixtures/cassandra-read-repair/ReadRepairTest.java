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

import org.junit.BeforeClass;
import org.junit.Test;

import org.apache.cassandra.SchemaLoader;
import org.apache.cassandra.config.DatabaseDescriptor;
import org.apache.cassandra.db.ConsistencyLevel;

import static org.junit.Assert.*;

/**
 * Unit tests for ReadRepair, covering read_repair_chance configuration
 * and background repair triggering behaviour.
 */
public class ReadRepairTest
{
    @BeforeClass
    public static void setupDD()
    {
        DatabaseDescriptor.daemonInitialization();
        SchemaLoader.prepareServer();
    }

    @Test
    public void testReadRepairChanceDisabled()
    {
        // When read_repair_chance is 0.0, repair should never be triggered
        DatabaseDescriptor.setReadRepairChance(0.0);
        assertFalse(ReadRepair.shouldPerformReadRepair(ConsistencyLevel.ONE));
    }

    @Test
    public void testReadRepairChanceAlwaysEnabled()
    {
        // When read_repair_chance is 1.0, repair should always be triggered
        DatabaseDescriptor.setReadRepairChance(1.0);
        assertTrue(ReadRepair.shouldPerformReadRepair(ConsistencyLevel.ONE));
    }

    @Test
    public void testEffectiveReadRepairChanceLocal()
    {
        DatabaseDescriptor.setDcLocalReadRepairChance(0.5);
        assertEquals(0.5, ReadRepair.effectiveReadRepairChance(true), 0.001);
    }

    @Test
    public void testEffectiveReadRepairChanceGlobal()
    {
        DatabaseDescriptor.setReadRepairChance(0.1);
        assertEquals(0.1, ReadRepair.effectiveReadRepairChance(false), 0.001);
    }

    @Test
    public void testValidateReadRepairChanceInRange()
    {
        // Values in [0.0, 1.0] should not throw
        ReadRepair.validateReadRepairChance(0.0);
        ReadRepair.validateReadRepairChance(0.5);
        ReadRepair.validateReadRepairChance(1.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testValidateReadRepairChanceTooHigh()
    {
        ReadRepair.validateReadRepairChance(1.1);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testValidateReadRepairChanceNegative()
    {
        ReadRepair.validateReadRepairChance(-0.1);
    }
}
